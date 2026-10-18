from pathlib import Path
import urllib.request,urllib.parse,json,concurrent.futures,hashlib
ROOT=Path('c2a_metadata');ROOT.mkdir(exist_ok=True)
def request_file(name,url,data=None,timeout=45):
 p=ROOT/name
 try:
  req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode() if data else None,headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.seoul.go.kr/'})
  with urllib.request.urlopen(req,timeout=timeout) as r:
   b=r.read();meta={'name':name,'url':url,'data':data,'status':r.status,'bytes':len(b),'content_type':r.headers.get('Content-Type'),'disposition':r.headers.get('Content-Disposition'),'sha256':hashlib.sha256(b).hexdigest()}
  p.write_bytes(b)
  return meta
 except Exception as e:return {'name':name,'url':url,'data':data,'error':str(e)}
endpoint='https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false'
jobs=[('living_definition.download',endpoint,{'infId':'DOWNLOAD','infSeq':'4','seq':'31'}),('living_manual.download',endpoint,{'infId':'DOWNLOAD','infSeq':'4','seq':'32'}),('living_code_official.download',endpoint,{'infId':'DOWNLOAD','infSeq':'4','seq':'18'}),('LOCAL_PEOPLE_DONG_202606.zip',endpoint,{'infId':'OA-14991','infSeq':'3','seq':'2606'}),('living_long.html','https://data.seoul.go.kr/dataList/OA-14992/S/1/datasetView.do',None),('living_temp.html','https://data.seoul.go.kr/dataList/OA-14993/S/1/datasetView.do',None),('kma_stn.html','https://data.kma.go.kr/tmeta/stn/selectStnList.do',None),('kma_400.html','https://data.kma.go.kr/tmeta/stn/selectStnDetail.do?isSelectStn=Y&pgmNo=82&stdStnNo=400',None)]
if __name__=='__main__':
 res=[]
 with concurrent.futures.ThreadPoolExecutor(4) as ex:
  futs=[ex.submit(request_file,*j) for j in jobs]
  for f in concurrent.futures.as_completed(futs):
   x=f.result();res.append(x);print(json.dumps(x,ensure_ascii=False),flush=True)
 (ROOT/'initial_public_fetch.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
