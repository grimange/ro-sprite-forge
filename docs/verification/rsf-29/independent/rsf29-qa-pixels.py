import json,pathlib,hashlib,io
from PIL import Image
root=pathlib.Path('/tmp/rsf29-browser-projects/rsf29-browser-1793406878461')
p=json.loads((root/'manifest.json').read_text());c=p['video_imports'][0]
assert [i['ordinal'] for i in c['items']]==[4,2,0]
assert [i['pts'] for i in c['items']]==[300,120,0]
rows=[]
for item in c['items']:
 n=item['ordinal'];data=bytearray()
 for y in range(16):
  for x in range(16):
   rgb=(255,n*10,255-n*20) if y==n and x<=n else (n*40+10,200-n*30,25+n*35)
   data.extend((*rgb,255))
 raw=(root/'blobs'/item['png_sha256']).read_bytes();actual=Image.open(io.BytesIO(raw)).convert('RGBA').tobytes()
 assert actual==bytes(data)
 rows.append({'ordinal':n,'pts':item['pts'],'rgba_sha256':hashlib.sha256(data).hexdigest(),'png_sha256':hashlib.sha256(raw).hexdigest()})
# Hand-construct crop(1,1,14,14), offset(1,1) to16x16, exactkey170/80/165.
expected=bytearray()
for y in range(16):
 for x in range(16):
  if not(1<=x<=14 and 1<=y<=14):pixel=(0,0,0,0)
  elif y==4 and x<=4:pixel=(255,40,175,255)
  else:pixel=(170,80,165,0)
  expected.extend(pixel)
sha='c47c90c05eb58b54757725ae8cdab92acdf57c33cd2f0548807c227cf9b7fdfe'
derived=Image.open(root/'blobs'/sha).convert('RGBA').tobytes()
assert derived==bytes(expected)
assert c['visual_review']=='UNVERIFIED'
result={'frames':rows,'derived_rgba_sha256':hashlib.sha256(derived).hexdigest(),'derived_png_sha256':sha,'video_review':c['visual_review'],'result':'PASS'}
pathlib.Path('/tmp/rsf29-qa-pixels.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
