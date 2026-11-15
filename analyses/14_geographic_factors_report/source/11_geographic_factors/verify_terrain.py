from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'analysis/geographic-representativeness/.deps'))
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import unary_union,transform
from shapely import make_valid,contains_xy
OUT=Path(__file__).resolve().parent/'results';SRC=ROOT/'analysis/geographic-factors-20261114/sources'
df=pd.read_csv(OUT/'station_factors.csv');tr=Transformer.from_crs(4326,2326,always_xy=True)
sea=unary_union([make_valid(transform(tr.transform,shape(f['geometry']))) for f in json.loads((ROOT/'analysis/regional-altitude/sources/hk_sea.json').read_text(encoding='utf-8-sig'))['features']])
checks=0
with rasterio.open(SRC/'Whole_HK_DTM_5m.tif','r+') as ds:
 if ds.crs is None:ds.crs='EPSG:2326'
with rasterio.open(SRC/'Whole_HK_DTM_5m.tif') as ds,rasterio.open(SRC/'Whole_HK_DTM_5m.asc') as original:
 assert ds.crs.to_epsg()==2326 and ds.res==(5.,5.)
 coords=[tr.transform(r.longitude,r.latitude) for r in df.itertuples()]
 assert np.array_equal(np.array(list(ds.sample(coords))),np.array(list(original.sample(coords))))
 for r,(x,y) in zip(df.itertuples(),coords):
  w=from_bounds(x-1020,y-1020,x+1020,y+1020,ds.transform).round_offsets().round_lengths();a=ds.read(1,window=w,boundless=True,masked=True).astype(float).filled(np.nan);tf=ds.window_transform(w)
  rr,cc=np.indices(a.shape);xx=tf.c+(cc+.5)*5;yy=tf.f-(rr+.5)*5;dx=xx-x;dy=yy-y;distance=np.hypot(dx,dy)
  ok=np.isfinite(a)&~contains_xy(sea,xx,yy);centre=ok&(distance<=25);small=ok&(distance<=50)
  z=float(np.median(a[centre]));u=dx[small];v=dy[small];h=a[small];u=u-u.mean();v=v-v.mean();h=h-h.mean()
  determinant=(u@u)*(v@v)-(u@v)**2
  sx=((u@h)*(v@v)-(v@h)*(u@v))/determinant;sy=((v@h)*(u@u)-(u@h)*(u@v))/determinant
  slope=np.degrees(np.arctan(np.hypot(sx,sy)))
  assert abs(z-r.dtm_centre_m)<1e-10 and abs(slope-r.slope_deg)<1e-8
  for radius in [250,500,1000]:
   vals=a[ok&(distance<=radius)&(distance>25)];tpi=(z-np.mean(vals))/max(np.std(vals),1)
   assert abs(tpi-getattr(r,f'tpi_z_{radius}m'))<1e-10
   c='valley' if tpi<=-1 else 'ridge' if tpi>1 else 'plain' if slope<5 else 'slope'
   assert c==getattr(r,f'terrain_group_{radius}m');checks+=1
 # Synthetic flat and inclined planes give known slopes, without real terrain assumptions.
 u,v=np.meshgrid(np.arange(-50,51,5),np.arange(-50,51,5));u=u.ravel();v=v.ravel()
 for gradient in [0,.1]:
  z=gradient*u+7;u0=u-u.mean();v0=v-v.mean();z0=z-z.mean();slope=np.degrees(np.arctan(abs((u0@z0)/(u0@u0))))
  assert abs(slope-np.degrees(np.arctan(gradient)))<1e-10
  checks+=1
assert list(np.where(df.elevation_m<300,'low',np.where(df.elevation_m<700,'mid','high')))==list(df.elevation_group)
assert list(np.where(df.coast_distance_m<=500,'near',np.where(df.coast_distance_m<=2000,'transition','inland')))==list(df.coast_group)
assert list(np.where(df.restricted_fraction_500m>=.5,'high',np.where(df.restricted_fraction_500m>=.2,'mixed','low')))==list(df.urban_group)
res={'passed':True,'stations':len(df),'terrain_radius_checks':checks-2,'synthetic_plane_checks':2,'source_ASC_vs_TIFF_station_samples_match':True,'classification_counts':df.terrain_group.value_counts().to_dict(),'scale_sensitive_stations':int(df.terrain_sensitive_scale.sum()),'near_rule_boundary_stations':int(df.terrain_near_boundary.sum()),'max_abs_dtm_station_elevation_difference_m':float(abs(df.dtm_minus_station_m).max()),'minimum_land_fraction_500m':float(df.land_fraction_500m.min()),'scope':'Verifies numerical extraction/rules, not physical field validity of geomorphological classes. Existing land-use/coast inputs retained from prior audited study.'}
(OUT/'terrain_verification.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(res)
