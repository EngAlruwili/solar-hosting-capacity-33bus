"""Render a local English-narrated explainer with Arabic subtitles.

Requires optional media dependencies and a locally downloaded Piper voice.
No network calls are made by this script. Run from the repository root.
"""
from pathlib import Path
import argparse
import json
import subprocess
import wave
import math
import textwrap
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from piper import PiperVoice, SynthesisConfig
import imageio_ffmpeg


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--arabic-font',type=Path,required=True)
    parser.add_argument('--latin-font',type=Path,default=Path('C:/Windows/Fonts/arial.ttf'))
    parser.add_argument('--output',type=Path,default=Path('media'))
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    scratch=out/'render';scratch.mkdir(exist_ok=True)
    remote=pd.read_csv('reports/study/hosting_summary.csv').query("placement == 'remote'")
    a=remote.loc[remote.control=='unity_pf','capacity_mw'].iloc[0]
    b=remote.loc[remote.control=='volt_var','capacity_mw'].iloc[0]
    scenes=[
    ('THE QUESTION','How much solar can a distribution feeder accommodate?',
     'كم طاقة شمسية تستطيع شبكة التوزيع استيعابها؟','intro'),
    ('A REPRODUCIBLE STUDY','This project uses Python and a thirty-three-bus benchmark to investigate voltage limits.',
     'نستخدم بايثون ونموذج شبكة من ثلاث وثلاثين نقطة لدراسة حدود الجهد.','network'),
    ('CHECK THE STARTING POINT','Before adding solar, the original feeder reached a minimum voltage of only ninety-one point three percent of nominal.',
     'قبل إضافة الطاقة الشمسية، بلغ أقل جهد في الشبكة الأصلية نحو واحد وتسعين فاصلة ثلاثة بالمئة من قيمته الاسمية.','baseline'),
    ('MAKE ASSUMPTIONS VISIBLE','The solar study uses a separate operating case, with source voltage set to one point zero three per unit.',
     'لدراسة الطاقة الشمسية، استخدمنا حالة تشغيل منفصلة بجهد مصدر مقداره واحد فاصلة صفر ثلاثة من القيمة الاسمية.','assumptions'),
    ('FOUR SYNTHETIC DAYS','Four synthetic demand and solar profiles are evaluated at fifteen-minute intervals. These are not field measurements.',
     'اختبرنا أربعة أنماط افتراضية للأحمال والشمس كل خمس عشرة دقيقة. هذه ليست قياسات ميدانية.','profiles'),
    ('LOCATION MATTERS','Solar is placed across the feeder, near the supply, or at remote buses. Each comparison uses the same installed capacity.',
     'وزّعنا الطاقة الشمسية عبر الشبكة، أو قرب المصدر، أو عند الأطراف، مع تثبيت السعة عند المقارنة.','locations'),
    ('SMART-INVERTER CONTROL','Volt-VAR control adjusts reactive power to support voltage, while respecting inverter capability limits.',
     'يعدّل التحكم بالعاكس القدرة غير الفعالة لدعم الجهد، مع الالتزام بحدود قدرة العاكس.','control'),
    ('THE REMOTE-SOLAR RESULT',f'For remote solar, the largest tested voltage-feasible capacity rose from about {a:.2f} to {b:.2f} megawatts with control.',
     'عند أطراف الشبكة، ارتفعت أكبر سعة مختبرة ضمن حدود الجهد من نحو واحد فاصلة ثلاثة وثمانين إلى ثلاثة فاصلة صفر اثنين ميجاواط.','result'),
    ('UNDERSTAND THE TRADEOFF','At the same installed capacity, control reduced peak voltage, but increased total line-loss energy by about five point six percent.',
     'عند السعة نفسها، خفّض التحكم أعلى جهد، لكنه زاد طاقة الفواقد في الخطوط بنحو خمسة فاصلة ستة بالمئة.','tradeoff'),
    ('CHECK THE CALCULATIONS','An independent radial solver was checked against pandapower at fifty-four operating points. Automated tests also check physical behavior.',
     'قارنّا طريقة حساب مستقلة مع بانداباور عند أربع وخمسين حالة تشغيل، وأضفنا اختبارات تلقائية للسلوك الكهربائي.','validation'),
    ('TEST THE ASSUMPTIONS','Sensitivity studies vary demand, source voltage, inverter size, and time resolution. The answer depends on these assumptions.',
     'اختبرنا أثر تغيّر الأحمال وجهد المصدر وحجم العاكس ودقة الزمن. النتيجة تعتمد على هذه الافتراضات.','sensitivity'),
    ('KNOW THE LIMITS','Some high-capacity control calculations did not converge. These remain unresolved, and are not treated as physical violations.',
     'بعض حسابات التحكم عند السعات العالية لم تتقارب. بقيت حالات غير محسومة، ولم نعتبرها تجاوزات كهربائية.','limits'),
    ('ENGINEERING YOU CAN INSPECT','The repository includes code, tests, result tables, and an engineering report. These voltage-only findings are not utility connection approval.',
     'المشروع يتضمن الكود والاختبارات والنتائج والتقرير. النتائج تخص الجهد فقط، وليست موافقة على الربط بالشبكة.','end')]
    voice=PiperVoice.load(str(args.model))
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    bg='#F2EFE6';ink='#172D31';teal='#147D86';gold='#CC9C4A'
    font=lambda size:ImageFont.truetype(str(args.latin_font),size)
    arabic=lambda size:ImageFont.truetype(str(args.arabic_font),size)
    reshaper=arabic_reshaper.ArabicReshaper(configuration=arabic_reshaper.config_for_true_type_font(str(args.arabic_font)))
    reshape=lambda s:get_display(reshaper.reshape(s))
    from fontTools.ttLib import TTFont
    cmap=TTFont(str(args.arabic_font)).getBestCmap()
    for _,_,caption,_ in scenes:
        missing={hex(ord(c)) for c in reshape(caption) if ord(c) not in cmap}
        if missing:raise ValueError(f'Unsupported subtitle glyphs: {missing}')
    def wrap(draw,text,face,width,rtl=False):
        lines=[];line=''
        for word in text.split():
            candidate=(line+' '+word).strip()
            display=reshape(candidate) if rtl else candidate
            if draw.textlength(display,font=face)>width and line:
                lines.append(line);line=word
            else:line=candidate
        return lines+[line]
    def center(draw,text,y,face,fill=ink):
        draw.text((960,y),text,font=face,fill=fill,anchor='mt')
    clips=[];timing=[];elapsed=0
    for idx,(title,en,ar,kind) in enumerate(scenes):
        image=Image.new('RGB',(1920,1080),bg);d=ImageDraw.Draw(image)
        d.text((90,50),'POWER SYSTEMS  /  PORTFOLIO STUDY',font=font(25),fill=teal)
        d.text((1830,50),f'{idx+1:02d} / {len(scenes):02d}',font=font(25),fill=teal,anchor='rt')
        d.line((90,100,1830,100),fill='#D7D8CE',width=2)
        center(d,title,132,font(54))
        if kind in ['intro','network','locations','end']:
            for branch,y in enumerate([335,440,545]):
                d.line((320,440,540,y,1530,y),fill=ink,width=5)
                for j in range(6):
                    x=560+j*185
                    d.ellipse((x-14,y-14,x+14,y+14),fill=teal if j<4 else gold)
            d.rounded_rectangle((220,400,330,480),12,fill=ink)
            d.text((275,420),'GRID',font=font(25),fill=bg,anchor='mt')
            center(d,'33 buses  |  12.66 kV  |  balanced radial benchmark',620,font(32))
            center(d,'Topology illustration — not a geographic map',670,font(23),teal)
        elif kind=='baseline':
            center(d,'0.913 p.u.',300,font(145),teal)
            center(d,'Original feeder  /  no solar',485,font(38))
            center(d,'Below the assumed 0.95 p.u. study threshold',560,font(32))
        elif kind=='assumptions':
            for x,big,small in [(430,'1.03','Source voltage (p.u.)'),(960,'0.95–1.05','Study voltage band'),(1490,'PQ','Constant-power loads')]:
                d.rounded_rectangle((x-245,300,x+245,600),22,fill='#E2E6DB')
                d.text((x,365),big,font=font(65),fill=teal,anchor='mt')
                d.text((x,490),small,font=font(27),fill=ink,anchor='mt')
        elif kind in ['profiles','sensitivity']:
            p=Path('reports/study')/('profiles.png' if kind=='profiles' else 'sensitivity.png')
            chart=Image.open(p).convert('RGB');chart.thumbnail((1450,490))
            image.paste(chart,((1920-chart.width)//2,220))
        elif kind=='control':
            d.line((470,470,1450,470),fill=ink,width=3);d.line((960,260,960,650),fill=ink,width=3)
            d.line((500,300,870,470,1050,470,1420,640),fill=teal,width=10)
            d.text((400,270),'Inject Q',font=font(30),fill=teal)
            d.text((1435,620),'Absorb Q',font=font(30),fill=teal)
            center(d,'Local voltage feedback + apparent-power limit',690,font(29))
            d.text((1470,470),'Voltage',font=font(25),fill=ink)
        elif kind=='result':
            for y,value,label,color in [(330,a,'Unity power factor',teal),(495,b,'Volt–VAR control',gold)]:
                d.text((210,y-48),label,font=font(31),fill=ink)
                d.rounded_rectangle((210,y,210+value/3.3*1200,y+80),12,fill=color)
                d.text((240+value/3.3*1200,y+20),f'{value:.2f} MW',font=font(38),fill=ink)
            center(d,'Simulated  |  four synthetic days  |  voltage-only criterion',665,font(27))
        elif kind=='tradeoff':
            center(d,'LOWER PEAK VOLTAGE',295,font(54),teal)
            center(d,'+5.6% loss energy',410,font(83),gold)
            center(d,'Equal solar capacity: 1.83 MW  |  four synthetic days',570,font(32))
        elif kind=='validation':
            center(d,'54',280,font(160),teal)
            center(d,'operating points checked against pandapower',490,font(40))
            center(d,'Power balance  •  Voltage  •  Losses  •  Inverter limits',590,font(30))
        else:
            center(d,'VOLTAGE STUDY ≠ CONNECTION APPROVAL',300,font(48),teal)
            for j,line in enumerate(['Numerical failures remain unresolved','No thermal, protection or dynamic assessment','Synthetic profiles are not an annual forecast']):
                center(d,line,425+j*75,font(35))
        # Separate English narration caption from the Arabic translation.
        en_lines=wrap(d,en,font(31),1700)
        for j,line in enumerate(en_lines):center(d,line,748+j*39,font(31))
        d.rounded_rectangle((70,861,1850,1042),20,fill=ink)
        ar_lines=wrap(d,ar,arabic(49),1650,True)
        if len(ar_lines)>2: raise ValueError('Arabic subtitle exceeds two lines')
        start=888 if len(ar_lines)==2 else 913
        for j,line in enumerate(ar_lines):center(d,reshape(line),start+j*63,arabic(49),bg)
        frame=scratch/f'{idx:02d}.png';image.save(frame)
        wav=scratch/f'{idx:02d}.wav'
        with wave.open(str(wav),'wb') as handle:
            voice.synthesize_wav(en,handle,syn_config=SynthesisConfig(length_scale=1.05))
        with wave.open(str(wav),'rb') as handle:duration=handle.getnframes()/handle.getframerate()+.7
        duration=math.ceil(duration*24)/24
        clip=scratch/f'{idx:02d}.mp4'
        subprocess.run([ffmpeg,'-y','-loglevel','error','-loop','1','-framerate','24','-i',str(frame),
            '-i',str(wav),'-vf',f'fade=t=in:st=0:d=0.2,fade=t=out:st={duration-.2}:d=0.2',
            '-af','apad','-t',str(duration),'-c:v','libx264','-preset','fast','-crf','21',
            '-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-ac','2',str(clip)],check=True)
        clips.append(clip);timing.append({'start':elapsed,'end':elapsed+duration,'english':en,'arabic':ar,'heading':title})
        elapsed+=duration
        print(f'Scene {idx+1}/{len(scenes)} rendered',flush=True)
    concat=scratch/'concat.txt'
    concat.write_text('\n'.join("file '"+p.resolve().as_posix()+"'" for p in clips),encoding='utf-8')
    subprocess.run([ffmpeg,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy',
                    '-movflags','+faststart',str(out/'solar-hosting-explainer.mp4')],check=True)
    def stamp(t):
        ms=round(t*1000);hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);seconds,ms=divmod(ms,1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}'
    for language in ['english','arabic']:
        content='\n\n'.join(f'{i+1}\n{stamp(t["start"])} --> {stamp(t["end"])}\n{t[language]}' for i,t in enumerate(timing))
        (out/f'{language}.srt').write_text(content+'\n',encoding='utf-8')
    (out/'script-and-timings.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2),encoding='utf-8')
    Image.open(scratch/'07.png').save(out/'poster.png')
    montage=Image.new('RGB',(1280,360*math.ceil(len(scenes)/2)),bg)
    for i in range(len(scenes)):
        im=Image.open(scratch/f'{i:02d}.png');im.thumbnail((640,360));montage.paste(im,((i%2)*640,(i//2)*360))
    montage.save(out/'contact-sheet.jpg')
    print(f'Finished {elapsed:.1f} seconds',flush=True)


if __name__=='__main__':main()
