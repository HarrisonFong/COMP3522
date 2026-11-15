"""Official 5 m DTM -> outcome-blind station terrain proxies. No database access."""
from pathlib import Path
import sys,json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'analysis/geographic-representativeness/.deps'))
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from rasterio.shutil import copy as rio_copy
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import unary_union,transform
from shapely import make_valid,contains_xy

HERE=Path(__file__).resolve().parent;OUT=HERE/'results';OUT.mkdir(exist_ok=True)
SRC=ROOT/'analysis/geographic-factors-20261114/sources'
geo=pd.read_csv(ROOT/'analysis/geographic-representativeness/results/station_geography.csv')
geo=geo[geo.primary_aws&(geo.temperature_candidate|geo.rain_candidate)].copy()
assert len(geo)==32
dtm=SRC/'Whole_HK_DTM_5m.tif'
if not dtm.exists():rio_copy(SRC/'Whole_HK_DTM_5m.asc',dtm,driver='GTiff',compress='DEFLATE',tiled=True)
with rasterio.open(dtm,'r+') as ds:
 if ds.crs is None:ds.crs='EPSG:2326' # Official source CRS; ASC has no embedded CRS.
trans=Transformer.from_crs(4326,2326,always_xy=True)
seafile=ROOT/'analysis/regional-altitude/sources/hk_sea.json'
sea=unary_union([make_valid(transform(trans.transform,shape(f['geometry']))) for f in json.loads(seafile.read_text(encoding='utf-8-sig'))['features']])
def klass(t,s,cut=1,slope=5):
 return 'valley' if t<=-cut else 'ridge' if t>cut else 'plain' if s<slope else 'slope'
rows=[]
with rasterio.open(dtm) as src:
 assert src.res==(5.,5.)
 for r in geo.itertuples():
  x,y=trans.transform(r.longitude,r.latitude)
  w=from_bounds(x-1020,y-1020,x+1020,y+1020,src.transform).round_offsets().round_lengths()
  ar=src.read(1,window=w,boundless=True,masked=True).astype(float).filled(np.nan)
  aff=src.window_transform(w);rr,cc=np.indices(ar.shape)
  xx=aff.c+(cc+.5)*5;yy=aff.f-(rr+.5)*5
  dx=xx-x;dy=yy-y;dist=np.hypot(dx,dy)
  marine=contains_xy(sea,xx,yy);valid=np.isfinite(ar)&~marine
  centre=valid&(dist<=25);plane=valid&(dist<=50)
  if centre.sum()<4 or plane.sum()<10:raise ValueError(f'insufficient central terrain at {r.station_code}')
  z0=float(np.median(ar[centre]));coef=np.linalg.lstsq(np.column_stack([dx[plane],dy[plane],np.ones(plane.sum())]),ar[plane],rcond=None)[0]
  slope=float(np.degrees(np.arctan(np.hypot(coef[0],coef[1]))))
  rec=r._asdict();rec.pop('Index',None)
  rec.update(dtm_centre_m=z0,dtm_minus_station_m=z0-r.elevation_m,slope_deg=slope,central_land_cells=int(centre.sum()))
  for radius in [250,500,1000]:
   mask=valid&(dist<=radius)&(dist>25)
   vals=ar[mask];assert len(vals)>=50
   mean=float(vals.mean());sd=float(vals.std());tpi=z0-mean
   z=tpi/max(sd,1.)
   rec.update({f'tpi_m_{radius}m':tpi,f'tpi_z_{radius}m':z,f'relief_{radius}m':float(np.quantile(vals,.95)-np.quantile(vals,.05)),f'land_fraction_{radius}m':float(mask.sum()/((dist<=radius)&(dist>25)).sum()),f'terrain_group_{radius}m':klass(z,slope)})
  rec['terrain_group']=rec['terrain_group_500m']
  rec['terrain_sensitive_scale']=len(set(rec[f'terrain_group_{r}m'] for r in [250,500,1000]))>1
  rec['terrain_near_boundary']=abs(abs(rec['tpi_z_500m'])-1)<.15 or abs(slope-5)<.5
  rec['terrain_group_cut075']=klass(rec['tpi_z_500m'],slope,.75)
  rec['terrain_group_cut125']=klass(rec['tpi_z_500m'],slope,1.25)
  rec['elevation_group']='low' if r.elevation_m<300 else 'mid' if r.elevation_m<700 else 'high'
  rec['log_coast_km']=np.log1p(r.coast_distance_m/1000)
  rows.append(rec)
df=pd.DataFrame(rows)
assert np.isfinite(df[['slope_deg','tpi_z_500m','relief_500m','elevation_m','log_coast_km','restricted_fraction_500m']]).all().all()
df.to_csv(OUT/'station_factors.csv',index=False,encoding='utf-8-sig')
spec={'download_url':'https://www.landsd.gov.hk/landsd_psi_data/SMO/data/Whole_HK_DTM_5m.zip','official_description':'https://www.landsd.gov.hk/en/spatial-data/open-data/kf_dtm.html','method_reference':'https://www.jennessent.com/downloads/Land_Facet_Tools_A4.pdf#page=55','access_date':'2026-11-14','dtm_description':'2017 product revised March 2019, photographs 2014/2015 according to official key features. This archived named product is not claimed to be the latest CSDI raster. Includes vegetation/above-ground features. EPSG2326, metres HK principal datum.','rules':'Central elevation median of land cells within 25 m. Local slope from plane fit within 50 m. TPI z=(central elevation-neighbour mean)/max(neighbour SD,1m), annulus 25m to R. Land/mapped cells only. Primary R500m; TPI<=-1 valley, >1 ridge, otherwise slope<5deg plain, otherwise slope. Operational proxies, not hydrological classification.','caveats':['Static historical terrain and contemporary coastline; coastline and terrain dates differ.','Coastal and small-island neighbourhoods are truncated to available land; land support reported, not replaced with sea zero.','Few stations mean landform groups and factors can be confounded; labels sensitive to scale/thresholds are retained, not removed.','Central DTM may differ from station height due to coordinates, station platform, vegetation or source differences.'],'counts':df.terrain_group.value_counts().to_dict(),'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC/'Whole_HK_DTM_5m.zip',SRC/'Whole_HK_DTM_5m.asc',seafile]}}
(OUT/'terrain_provenance.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
print(df[['station_code','elevation_m','dtm_centre_m','slope_deg','tpi_z_500m','terrain_group','terrain_sensitive_scale','land_fraction_500m']].to_string(index=False),flush=True)
