"""Render the public evidence film with Gemini TTS, motion graphics and captions.

Uses existing gcloud login; never persists credentials. Visuals reconstruct the
sanitized actual Switch handoffs and are explicitly labeled as archived evidence.
Optional authoring tools: Pillow, ffmpeg, ffprobe, gcloud.
"""
import base64, concurrent.futures, json, math, subprocess, textwrap, urllib.request, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/video-gemini'
OUT=ROOT/'website/dist'
MODEL='gemini-2.5-flash-tts'
SCENES=[
 ('01 / THE PROBLEM','A patch is a claim.','Evidence makes it reviewable.',
 'An AI can suggest a fix in seconds. But who reproduced the bug? Which code was tested? And did the fix really work? PatchRoom brings those answers into one Switch room. This film presents archived evidence from an actual three-agent run.',
 'hero'),
 ('02 / THE WORKFLOW','Three agents. One room.','Explicit handoffs. Shared context. Preserved evidence.',
 'A triager reproduces the issue. An engineer authors a minimal candidate. A verifier independently checks the result. Switch connects their conversation and handoffs. PatchRoom preserves the state, source snapshots, test contract and proposal history for review.',
 'flow'),
 ('03 / TRIAGER','The boundary that broke.','A $100 order. A $5 mistake.',
 'The report is simple. Shipping should be free at one hundred dollars or more. At exactly one hundred, the checkout still charges five. In the actual automated case, the triager ran six checks. Two assertions failed. The failure was reproduced before a fix was proposed.',
 'triager'),
 ('04 / ENGINEER','One character. Clear intent.','Include equality. Preserve the contract.',
 'The engineer found the cause: a strict greater-than comparison excludes the boundary. The authored candidate adds equality. One source file changes. The baseline and protected tests stay intact. The engineer then hands the candidate to a separate verifier.',
 'diff'),
 ('05 / VERIFIER','A fix with receipts.','Same six checks. Separate source copies.',
 'The verifier reruns both copies against the same saved contract. The baseline still fails two assertions. The candidate passes all six checks, with no errors or skips. Source and contract hashes identify exactly what was tested. The review packet preserves the diff and command output.',
 'verify'),
 ('06 / HUMAN REVIEW','Know when to stop.','awaiting_human_review  /  decision: null',
 'Passing tests does not grant approval. This was an automated local report, with no authenticated human reporter. The installed Switch version omits sender-type metadata required by our review gate. PatchRoom stops at awaiting human review. No acceptance or merge is claimed.',
 'review'),
 ('07 / EXPLORE','Inspect the evidence.','Reproduce the workflow. Make the decision.',
 'Thirty-five workflow and integration tests pass locally and in GitHub Actions. Explore the source, real handoffs and verification evidence. The public Texmed deployment hosts this walkthrough. Agents run locally through Switch Console. PatchRoom: three agents, one reviewable fix.',
 'end')]
REG='/System/Library/Fonts/Supplemental/Arial.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf';MONO='/System/Library/Fonts/Menlo.ttc'
def font(n,b=False,m=False):return ImageFont.truetype(MONO if m else BOLD if b else REG,n)
def call(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout

def voice(index,token):
 path=WORK/f'voice-{index}.wav'
 if path.exists(): return path
 text=SCENES[index][3]
 prompt='Narrate this product documentary in a warm, assured, intelligent voice. Crisp articulation, expressive but restrained, conversational rhythm, about 155 words per minute. Short natural pauses between sentences. Speak only the narration, with no introduction or sound effects. Narration: '+text
 payload={'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'responseModalities':['AUDIO'],'speechConfig':{'voiceConfig':{'prebuiltVoiceConfig':{'voiceName':'Kore'}}}}}
 url=f'https://us-central1-aiplatform.googleapis.com/v1beta1/projects/billing-dashboard-505116/locations/us-central1/publishers/google/models/{MODEL}:generateContent'
 req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','x-goog-user-project':'billing-dashboard-505116'})
 with urllib.request.urlopen(req,timeout=180) as r: result=json.load(r)
 pcm=b''.join(base64.b64decode(p['inlineData']['data']) for p in result['candidates'][0]['content']['parts'] if 'inlineData' in p)
 if not pcm:raise RuntimeError('No audio returned')
 with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(pcm)
 print(f'Gemini narration {index+1}/{len(SCENES)} ready',flush=True)
 return path

def panel(d,box,fill='#132832',outline='#29434b'):
 d.rounded_rectangle(box,radius=24,fill=fill,outline=outline,width=2)
def txt(d,xy,text,size=32,color='#eaf3f2',bold=False,mono=False):d.text(xy,text,font=font(size,bold,mono),fill=color)
def wrapped(d,xy,text,width=65,size=29,color='#b9cfce',step=43,mono=False):
 for k,line in enumerate(textwrap.wrap(text,width)):txt(d,(xy[0],xy[1]+k*step),line,size,color,mono=mono)
def frame(i):
 label,title,sub,_,kind=SCENES[i]
 im=Image.new('RGB',(1920,1080));d=ImageDraw.Draw(im)
 for y in range(1080):
  a=y/1080;d.line((0,y,1920,y),fill=(int(8+7*a),int(20+12*a),int(27+11*a)))
 for x in range(0,1920,80):d.line((x,0,x,1080),fill='#142a32')
 for y in range(0,1080,80):d.line((0,y,1920,y),fill='#142a32')
 d.rounded_rectangle((80,62,91,96),radius=4,fill='#b9f26a');txt(d,(110,60),'PATCHROOM',32,bold=True)
 txt(d,(1240,69),'FLIP THE SWITCH  /  2026',22,'#89aaa9',mono=True)
 txt(d,(90,169),label,23,'#b9f26a',True);txt(d,(86,218),title,80,bold=True);txt(d,(90,325),sub,33,'#b9cfce')
 if kind=='hero':
  for x,n,a,c in [(90,'01','REPRODUCE','#ff987e'),(665,'02','PATCH','#d5bdff'),(1240,'03','VERIFY','#b9f26a')]:
   panel(d,(x,455,x+530,817));txt(d,(x+36,492),n,28,c,mono=True);txt(d,(x+36,559),a,43,c,True)
   wrapped(d,(x+36,638),{'01':'Show the failure. Save the baseline.','02':'Author a candidate. Preserve the tests.','03':'Run both copies. Keep the receipts.'}[n],25,29)
  txt(d,(90,861),'FROM BUG REPORT TO REVIEW EVIDENCE',26,'#89aaa9',mono=True)
 elif kind=='flow':
  labels=[('TRIAGER','Reproduction'),('ENGINEER','Candidate patch'),('VERIFIER','Independent checks'),('HUMAN','Review gate')]
  for j,(name,detail) in enumerate(labels):
   x=90+j*445;panel(d,(x,490,x+395,730));txt(d,(x+26,530),name,32,'#b9f26a' if j==2 else '#eaf3f2',True);txt(d,(x+26,603),detail,26,'#b9cfce')
   if j<3:txt(d,(x+405,570),'→',36,'#b9f26a')
  panel(d,(90,790,1820,905));txt(d,(130,824),'SWITCH ROOM   /   identities + shared context + explicit handoffs',28,mono=True)
 elif kind=='triager':
  panel(d,(90,435,760,895));txt(d,(130,477),'CHECKOUT FIXTURE',25,'#89aaa9',mono=True);txt(d,(130,548),'$100.00',100,bold=True);txt(d,(130,688),'Expected shipping   $0',34,'#b9f26a');txt(d,(130,751),'Actual shipping     $5',34,'#ff987e')
  panel(d,(800,435,1820,895));txt(d,(840,477),'ACTUAL ARCHIVED HANDOFF / TRIAGER',23,'#b9f26a',mono=True)
  wrapped(d,(840,540),'“6 tests ran, 2 assertion failures at exactly $100 (string and Decimal inputs); expected $0, actual $5.”',43,31,step=47)
  txt(d,(840,800),'live-dev-001  ·  automated report',26,'#89aaa9',mono=True)
 elif kind=='diff':
  panel(d,(90,435,1820,895));txt(d,(135,475),'checkout.py  /  CANDIDATE DIFF',25,'#89aaa9',mono=True)
  d.rounded_rectangle((130,550,1780,650),radius=12,fill='#3d262a');txt(d,(166,576),'- amount > Decimal("100.00")',42,'#ffb2a3',mono=True)
  d.rounded_rectangle((130,675,1780,775),radius=12,fill='#203b2b');txt(d,(166,701),'+ amount >= Decimal("100.00")',42,'#c8f39d',mono=True)
  txt(d,(137,820),'One source file changed. Protected tests preserved.',29,'#b9cfce')
 elif kind=='verify':
  for x,name,note,c in [(90,'BASELINE','2 assertion failures','#ff987e'),(980,'CANDIDATE','0 failures · 0 skips','#b9f26a')]:
   panel(d,(x,435,x+840,780));txt(d,(x+40,477),name,29,c,True);txt(d,(x+40,542),'6 checks',80,bold=True);txt(d,(x+40,665),note,34,c)
  panel(d,(90,815,1820,913));txt(d,(130,846),'SAME CONTRACT  a6e7cdc43bc1…   /   CANDIDATE  aee43e9c3ba5…',26,'#b9cfce',mono=True)
 elif kind=='review':
  panel(d,(90,435,1820,900));txt(d,(140,485),'VERIFIED ≠ APPROVED',51,'#efcc8a',True)
  for j,line in enumerate(['Automated case: no authenticated human reporter','Installed Switch omits required sender-type metadata','Human review stays blocked; no acceptance or merge']):
   txt(d,(146,595+j*77),'•  '+line,33,'#b9cfce')
  txt(d,(144,842),'SAFE STOP / explicit state, preserved evidence',25,'#efcc8a',mono=True)
 else:
  txt(d,(90,450),'35',172,'#b9f26a',True);txt(d,(360,508),'passing workflow + integration tests',45,bold=True)
  txt(d,(365,576),'Local verification + GitHub Actions',30,'#b9cfce')
  panel(d,(90,710,1820,908));txt(d,(135,747),'github.com/gowtham66867/patchroom',43,'#eaf3f2',mono=True);txt(d,(135,822),'Texmed Cloud Run demo  ·  Source  ·  Actual handoffs  ·  Test evidence',29,'#b9cfce')
 txt(d,(90,1008),'ARCHIVED ACTUAL RUN  /  EDITED EVIDENCE WALKTHROUGH  /  GEMINI NARRATION',20,'#89aaa9',mono=True)
 txt(d,(1745,1008),f'{i+1:02} / 07',20,'#89aaa9',mono=True)
 path=WORK/f'frame-{i}.png';im.save(path)
 if i==0:im.save(OUT/'gemini-poster.png')
 return path

def stamp(x):
 m=int(x*1000);return f'{m//3600000:02}:{m//60000%60:02}:{m//1000%60:02}.{m%1000:03}'
def main():
 WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 token=call(['gcloud','auth','print-access-token','--account=gowtham@texmed.us']).strip()
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(lambda i:voice(i,token),range(len(SCENES))))
 cues=['WEBVTT\n'];elapsed=0;metadata=[]
 for i,scene in enumerate(SCENES):
  audio=WORK/f'voice-{i}.wav';image=frame(i)
  with wave.open(str(audio)) as f:duration=f.getnframes()/f.getframerate()+.65
  segment=WORK/f'film-{i}.mp4'
  if not segment.exists():
   call(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-i',str(image),'-i',str(audio),'-vf',"scale=1960:1102,crop=1920:1080:x='20+10*sin(t/4)':y='11+5*sin(t/5)',fade=t=in:st=0:d=0.35",'-t',str(duration),'-r','24','-c:v','libx264','-preset','veryfast','-crf','21','-threads','3','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=9,apad',str(segment)])
  sentences=[s.strip()+'.' for s in scene[3].rstrip('.').split('. ')];weights=[len(s) for s in sentences];total=sum(weights);offset=elapsed
  for s,w in zip(sentences,weights):
   end=offset+duration*w/total;cues.append(stamp(offset)+' --> '+stamp(end)+'\n'+s+'\n');offset=end
  metadata.append({'scene':i+1,'title':scene[1],'start':round(elapsed,2),'duration':round(duration,2)});elapsed+=duration
  print('Scene rendered',i+1,flush=True)
 (WORK/'film-list.txt').write_text(''.join("file '"+str(WORK/f'film-{i}.mp4')+"'\n" for i in range(len(SCENES))))
 call(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(WORK/'film-list.txt'),'-c','copy','-movflags','+faststart',str(OUT/'gemini-walkthrough.mp4')])
 (OUT/'gemini-captions.vtt').write_text('\n'.join(cues));(OUT/'gemini-transcript.txt').write_text('\n\n'.join(s[3] for s in SCENES)+'\n')
 (OUT/'gemini-video.json').write_text(json.dumps({'model':MODEL,'voice':'Kore','duration':round(elapsed,2),'presentation':'Edited archived-evidence motion graphics; not a live execution recording','scenes':metadata},indent=2)+'\n')
 print(json.dumps({'video':str(OUT/'gemini-walkthrough.mp4'),'seconds':round(elapsed,2)}))
if __name__=='__main__':main()
