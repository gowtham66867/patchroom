"""Create an explicitly labeled evidence presentation, not a live screen recording.

Optional authoring dependencies: Pillow, ffmpeg/ffprobe and macOS say.
The application CLI itself has no dependency on these tools.
"""
import argparse
import json
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SLIDES=[
('THE PROBLEM','Bug reported. Fix proven.',
 ['Bug report in chat → investigation in a terminal', 'AI patch → uncertainty about what was tested', 'PatchRoom connects the entire evidence trail.'],
 'PatchRoom brings bug reproduction, patch generation and independent verification into one Switch room. This is a walkthrough of evidence from an actual three agent run on November sixth. It is not a recording of live execution. The test report was explicitly automated.'),
('01 / TRIAGER','Reproduce the actual failure.',
 ['CASE live-dev-001', 'Expected: free shipping at $100 or more', 'Observed: exactly $100 still costs $5', '6 tests ran. 2 assertions failed. Exit code 1.'],
 'The checkout policy says shipping is free at one hundred dollars or more. The triager ran the saved regression contract. Six tests executed. Two assertions failed at the exact one hundred dollar boundary, for string and decimal inputs. The agent posted the failure and handed the case to the engineer through Switch.'),
('02 / ENGINEER','A one-line candidate.',
 ['Root cause: a strict comparison excludes equality.', '', '- amount > Decimal("100.00")', '+ amount >= Decimal("100.00")', '', 'Baseline and protected contract remain unchanged.'],
 'The engineer inspected the evidence and authored a separate candidate file. The strict greater than comparison excluded equality. The candidate changes it to greater than or equal to. This was authored by the live engineer agent, rather than produced by the scripted replay. The engineer handed the candidate and explanation to the verifier.'),
('03 / VERIFIER','The same contract. Two copies.',
 ['BASELINE RECHECK    6 tests / 2 failures / exit 1', 'CANDIDATE          6 tests / 0 failures / exit 0', '', 'No errors. No skipped tests.', 'Independent verification by the verifier agent.'],
 'The verifier independently checked both source copies against the same saved contract. The baseline still failed the original two assertions. The candidate passed all six checks, with no errors or skips. The review packet preserves command output, the source diff, source hashes, and the protected contract hash.'),
('04 / REVIEW','Stop for an identifiable person.',
 ['State: awaiting_human_review', 'Decision: null', '', 'This automated local case has no human reporter.', 'Switch 0.31 omits required sender-type metadata.', 'No approval, merge or deployment was recorded.'],
 'PatchRoom stopped at awaiting human review. No human decision was recorded. This was an automated local case, and Switch version zero point thirty one omits the sender type metadata required by the review checks. The application refuses to infer identity from a display name. Passing these tests proves configured fixture behavior, not production correctness.'),
('TRY THE PROJECT','Inspect. Reproduce. Review.',
 ['35 workflow and integration tests pass.', '3 real coding agents collaborate through Switch.', '', 'github.com/gowtham66867/patchroom', 'python3 -m patchroom demo --case-id my-demo'],
 'The repository includes thirty five passing workflow and integration tests, an additional configured Python repository example, restart recovery, preserved proposal attempts, and the three agent Switch template. Explore the actual evidence and source repository from the project page. The hosted walkthrough presents archived results. Run the coding workflow locally through Switch Console.')]


def run(command):
 return subprocess.run(command,check=True,capture_output=True,text=True)


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--work',type=Path,default=ROOT/'work/video')
 args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True);args.work.mkdir(parents=True,exist_ok=True)
 fonts=Path('/System/Library/Fonts')
 regular=str(fonts/'Supplemental/Arial.ttf');bold=str(fonts/'Supplemental/Arial Bold.ttf');mono=str(fonts/'Menlo.ttc')
 durations=[];narrations=[]
 for index,(label,title,lines,narration) in enumerate(SLIDES):
  image=Image.new('RGB',(1280,720),'#142e27');draw=ImageDraw.Draw(image)
  draw.text((65,45),'PATCHROOM',font=ImageFont.truetype(bold,24),fill='#d8ef72')
  draw.text((65,100),'ARCHIVED EVIDENCE WALKTHROUGH · ACTUAL AGENT RUN',font=ImageFont.truetype(regular,16),fill='#b3c6b6')
  draw.text((65,155),label,font=ImageFont.truetype(bold,16),fill='#d8ef72')
  draw.text((65,194),title,font=ImageFont.truetype(bold,50),fill='#f6f5ef')
  draw.rounded_rectangle((60,280,1220,600),radius=14,fill='#10241e',outline='#405946')
  y=315
  for line in lines:
   for wrapped in textwrap.wrap(line,width=78) or ['']:
    draw.text((90,y),wrapped,font=ImageFont.truetype(mono,21),fill='#d8e7c7');y+=37
  draw.text((65,640),'Not a live screen recording. No human acceptance recorded.',font=ImageFont.truetype(regular,17),fill='#b3c6b6')
  draw.text((1130,640),f'{index+1} / {len(SLIDES)}',font=ImageFont.truetype(mono,17),fill='#d8ef72')
  frame=args.work/f'slide-{index}.png';image.save(frame)
  if index==0:image.save(args.output/'poster.png')
  audio=args.work/f'narration-{index}.aiff'
  if not audio.exists():
   run(['/usr/bin/say','-v','Samantha','-r','155','-o',str(audio),narration])
  duration=float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(audio)]).stdout)+0.8
  segment=args.work/f'segment-{index}.mp4'
  valid=False
  if segment.exists() and segment.stat().st_size:
   try: run(['ffprobe','-v','error',str(segment)]);valid=True
   except subprocess.CalledProcessError: pass
  if not valid: run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-i',str(frame),'-i',str(audio),'-t',str(duration),'-c:v','libx264','-tune','stillimage','-preset','ultrafast','-threads','2','-r','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','112k','-af','apad',str(segment)])
  durations.append(duration);narrations.append(narration)
 (args.work/'segments.txt').write_text(''.join("file '"+str((args.work/f'segment-{i}.mp4').resolve())+"'\n" for i in range(len(SLIDES))))
 run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(args.work/'segments.txt'),'-c','copy','-movflags','+faststart',str(args.output/'walkthrough.mp4')])
 def stamp(seconds):
  ms=int(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
 cues=['WEBVTT\n'];elapsed=0
 for duration,narration in zip(durations,narrations):
  sentences=[x.strip()+'.' for x in narration.rstrip('.').split('. ') if x.strip()]
  per=duration/len(sentences)
  for sentence in sentences:
   cues.append(stamp(elapsed)+' --> '+stamp(elapsed+per)+'\n'+sentence+'\n');elapsed+=per
 (args.output/'captions.vtt').write_text('\n'.join(cues))
 (args.output/'walkthrough-transcript.txt').write_text('\n\n'.join(narrations)+'\n')
 print(json.dumps({'video':str(args.output/'walkthrough.mp4'),'duration_seconds':round(sum(durations),1),'type':'narrated archived-evidence presentation; not live screen recording'}))


if __name__=='__main__':main()
