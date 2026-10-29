"""Verify cold boot pixels/timing and the visible terminal footer in openMSX."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,statistics,math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine,tcl,scanout_recording_tcl
from scripts.msx.screen5 import rgb333,expand
from PIL import Image

def verify(bundle):
    bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='boot-proof-',dir=bundle))
    for a,b in (('fixed-hud.rom','measured.rom'),('lab.sym','measured.sym')):shutil.copyfile(bundle/a,out/b)
    s={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(out/'measured.sym').read_text())}
    meta=json.loads((bundle/'session-boot.json').read_text());frames=meta['sample_frames']
    title=json.loads((bundle/'session-title.json').read_text())
    bank=json.loads((bundle/'session-build.json').read_text())['banks']['SESSION_BANK']
    ui_prefix=(out/'measured.rom').read_bytes()[bank*16384:bank*16384+16].hex()
    code=f'''set save_settings_on_exit false
set renderer SDLGL-PP
set sound_driver null
set throttle off
set minframeskip 0
set maxframeskip 0
set vsync off
set z80_freq 3579545
set z80_freq_locked true
set limitsprites true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking boot_cosmetics_proof
{scanout_recording_tcl(out,s['boot'])}
set index 0;set ready 0;set title_seen {{}};set out {tcl(out)}
set log [open [file join $out times.tsv] w]
set costs [open [file join $out ui-costs.tsv] w]
set token 0;array set calls {{}}
set ui_prefix [binary format H* {ui_prefix}]
proc cost_enter {{name}} {{
 set sp [reg SP];set ret [expr {{[debug read memory $sp]+256*[debug read memory [expr {{$sp+1}}]]}}]
 set n [incr ::token]
 set bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$sp+2}}]" "cost_leave $n"]
 set ::calls($n) [list $name [machine_info time] $bp]
}}
proc cost_leave {{n}} {{
 lassign $::calls($n) name start bp
 puts $::costs "$name [expr {{([machine_info time]-$start)*3579545}}]"
 debug remove_bp $bp;unset ::calls($n)
}}
proc dump {{name}} {{
 set f [open [file join $::out "$name.vram"] wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f
 set f [open [file join $::out "$name.regs"] wb];puts -nonewline $f [debug read_block {{VDP regs}} 0 64];close $f
}}
set VDP.too_fast_vram_access_callback {{puts stderr "Boot VRAM timing violation";exit 2}}
debug set_bp {s['GameSession_BootShow']} {{}} {{puts $::log "start [machine_info time]"}}
debug set_bp {s['GameSession_BootShow.published']} {{}} {{
 dump boot-$::index
 foreach r {{8 9 10}} {{if {{[debug read {{PSG regs}} $r]}} {{puts stderr "Boot retained audio";exit 2}}}}
 set elapsed_ticks [expr {{([debug read memory {s['clock_ticks']}]+256*[debug read memory {s['clock_ticks']+1}]-[debug read memory {s['GameSession_BootStartTick']}]-256*[debug read memory {s['GameSession_BootStartTick']+1}])&65535}}]
 puts $::log "$::index [machine_info time] $elapsed_ticks";incr ::index
 if {{$::index=={len(frames)}}} {{after time 0.04 {{screenshot -raw [file join $::out matrix.png]}}}}
}}
debug set_bp {s['GameSession_BootShow.done']} {{}} {{puts $::log "done [machine_info time]";flush $::log}}
proc poll {{}} {{
 if {{[debug read memory 0xc7d0]==1 && [debug read memory 0xc7dd] && !$::ready}} {{
  set ::ready 1;dump cast
  screenshot -raw [file join $::out cast.png]
 }}
 if {{$::ready && [debug read memory 0xc7d0]==1 && [debug read memory 0xdfe7]}} {{
  set phase [debug read memory {s['UI_CastBlink']}]
  if {{$phase ni $::title_seen}} {{
   lappend ::title_seen $phase
   set name [expr {{$phase==0?"title-on":"title-off"}}]
   dump $name;screenshot -raw [file join $::out "$name.png"]
  }}
  if {{[llength $::title_seen]==2}} {{catch {{record stop}};close $::log;close $::costs;exit 0}}
 }}
 after time 0.02 poll
}}
after time 0.02 poll
after time 90 {{puts stderr "Boot/title timeout PC=[reg PC] state=[debug read memory 0xc7d0] done=[debug read memory 0xdfe7]";exit 3}}
'''
    for name in ('UI_CastFooter_Tick','UI_MSXLogo_Draw'):
        if name in s:code+=f'debug set_bp {s[name]} {{[debug read_block memory 0x8000 16] eq $::ui_prefix}} {{cost_enter {name}}}\n'
    (out/'probe.tcl').write_text('if {[catch {\n'+code+'\n} e]} {puts stderr $::errorInfo;exit 2}\n')
    with (out/'openmsx.log').open('w') as log:
        run=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert run.returncode==0,(out,(out/'openmsx.log').read_text()[-800:])
    colors=[tuple(c) for c in meta['palette']]
    for i,n in enumerate(frames):
        src=list(Image.open(Path(meta['frame_paths'][i])).convert('RGB').get_flattened_data())
        pix=[colors.index(src[y*288+x]) for y in range(212) for x in list(range(200))+list(range(232,288))]
        wanted=bytes(a*16+b for a,b in zip(pix[::2],pix[1::2]))
        regs=(out/f'boot-{i}.regs').read_bytes();vram=(out/f'boot-{i}.vram').read_bytes();base=(regs[2]&96)*1024
        assert vram[base:base+27136]==wanted,('Boot differs from captured original pixels',i,n)
        assert regs[7]&15==0,('Hardware-check border is not the black boot-palette entry',i,regs[7])
    matrix=Image.open(out/'matrix.png').convert('RGB')
    assert matrix.size==(320,240)
    border=[matrix.getpixel((x,y)) for y in range(240) for x in range(320)
            if x<32 or x>=288 or y<14 or y>=226]
    assert set(border)=={(0,0,0)},('Captured offscreen border is not black',set(border))
    times={row.split()[0]:float(row.split()[1]) for row in (out/'times.tsv').read_text().splitlines()}
    elapsed=times['done']-times['start']
    publication_errors=[times[str(i)]-times['start']-tick*59736/3579545 for i,tick in enumerate(meta['publication_ticks'])]
    # The start timestamp is between software-clock IRQ edges. Verify the actual
    # scheduler's ticks, then physical cadence relative to the first nonblack
    # publication. A constant IRQ/start phase must not look like a missed frame.
    actual_ticks={row.split()[0]:int(row.split()[2]) for row in (out/'times.tsv').read_text().splitlines() if row.split()[0].isdigit()}
    assert all(actual_ticks[str(i)]==tick for i,tick in enumerate(meta['publication_ticks']) if i>0),actual_ticks
    publication_phase=publication_errors[1]
    cadence_errors=[v-publication_phase for v in publication_errors[1:]]
    assert max(abs(v) for v in cadence_errors)<59736/3579545,cadence_errors
    assert abs(elapsed-meta['seconds'])<2*59736/3579545,(elapsed,meta['seconds'])
    build=json.loads((bundle/'session-build.json').read_text());rom=(out/'measured.rom').read_bytes();banks=build['banks']
    image=b''.join(rom[banks[n]*16384:(banks[n]+1)*16384] for n in ('SESSION_IMAGE_BANK','SESSION_DATA_BANK'))
    production=Path(build['production_bundle'])
    defs={n:int(v[1:],16) if v.startswith('$') else int(v) for n,v in re.findall(r'(?m)^(\w+) EQU (\$[\da-fA-F]+|\d+)\s*$',(production/'config.inc').read_text())}
    source_rom=(production/'raster-scroll.rom').read_bytes()
    source_image=b''.join(source_rom[defs[n]*16384:(defs[n]+1)*16384] for n in ('SESSION_IMAGE_BANK','SESSION_DATA_BANK'))
    assert image[:176*128]==source_image[8*128:184*128],'Static original title was changed beyond its8px move'
    red=defs['RED']
    unpack=lambda data:bytes(v for b in data for v in (b>>4,b&15))
    original_pixels=unpack(source_image[:27136]);title_pixels=unpack(image[:27136])
    # The approved native PNG is the oracle. No resampling, RGB thresholding,
    # inferred glyphs or generated mask may redefine its geometry or holes.
    reference=Image.open(ROOT/'references/exports/namco-retrowork/namco-retrowork-162x10.png').convert('RGBA')
    assert reference.size==(162,10)
    rx,ry=47,198
    for y in range(195,212):
        for x in range(256):
            wanted=original_pixels[0]
            if rx<=x<rx+162 and ry<=y<ry+10 and reference.getpixel((x-rx,y-ry))[3]==255:wanted=red
            assert title_pixels[y*256+x]==wanted,('Signature differs from approved PNG at1:1',x,y)
    assert title['brand_x']==rx and title['brand_y']==ry
    assert 212-ry-reference.height==4
    bx,by,bw,bh=(title[k] for k in ('brand_x','brand_y','brand_width','brand_height'))
    mask=(bundle/'session-title-brand-mask.bin').read_bytes();assert len(mask)==bw*bh
    assert all(title_pixels[(by+y)*256+bx+x]==(red if mask[y*bw+x] else original_pixels[0]) for y in range(bh) for x in range(bw)),'User wordmark mask changed'
    entries=lambda text:re.findall(r'dw UI_Reveal(\d+),(\d+)\s+db (\d+),(\d+),(\d+)',text)
    before=entries((production/'full-ui-data.inc').read_text());after=entries((bundle/'full-ui-data.inc').read_text())
    assert len(before)==len(after)==96
    for old,new in zip(before,after):
        assert old[0]==new[0] and int(old[1])-8*128==int(new[1]) and old[2:]==new[2:],'Original reveal geometry/delay changed'
        assert (production/f'ui-reveal-{old[0]}.bin').read_bytes()==(bundle/f'ui-reveal-{old[0]}.bin').read_bytes(),'Original reveal glyph changed'
    regs=(out/'cast.regs').read_bytes();assert regs[7]&15==defs['BLACK'],'Title border index was not restored'
    vram=(out/'cast.vram').read_bytes();base=(regs[2]&96)*1024
    expected=bytearray(image[:27136])
    for index,dest,width,height in re.findall(r'dw UI_Reveal(\d+),(\d+)\s+db (\d+),(\d+),\d+', (bundle/'full-ui-data.inc').read_text()):
        dest,width,height=map(int,(dest,width,height));blob=(bundle/f'ui-reveal-{index}.bin').read_bytes()
        for y in range(height):expected[dest+y*128:dest+y*128+width]=blob[y*width:(y+1)*width]
    if title['logo']['enabled']:
        x,y,w,h=title['logo']['rect'];blob=(bundle/'session-msx-logo.bin').read_bytes()
        for yy in range(h):expected[(y+yy)*128+x//2:(y+yy)*128+(x+w)//2]=blob[yy*w//2:(yy+1)*w//2]
    else:assert 'UI_MSXLogo_Draw' not in s,'Disabled module still emitted executable code'
    for state in ('on','off'):
        wanted=bytearray(expected)
        if state=='off':
            for i,(x,y,w,h) in enumerate(title['blink_rects']):
                blob=(bundle/f'session-title-key-{i}-off.bin').read_bytes()
                for yy in range(h):wanted[(y+yy)*128+x//2:(y+yy)*128+(x+w)//2]=blob[yy*w//2:(yy+1)*w//2]
        vram=(out/f'title-{state}.vram').read_bytes();regs=(out/f'title-{state}.regs').read_bytes();base=(regs[2]&96)*1024
        assert vram[base:base+27136]==wanted,('Complete cast pixels differ',state)
    grouped={}
    for row in (out/'ui-costs.tsv').read_text().splitlines():
        name,value=row.split();grouped.setdefault(name,[]).append(float(value))
    title_costs=[dict(name=n,calls=len(v),inclusive=dict(mean=statistics.mean(v),p95=sorted(v)[math.ceil(.95*len(v))-1],max=max(v))) for n,v in grouped.items()]
    report=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),path=str(out),boot_frames=len(frames),seconds=elapsed,
                target_seconds=meta['seconds'],max_state_timing_error_ms=max(abs(v) for v in cadence_errors)*1000,publication_phase_ms=publication_phase*1000,software_publication_ticks_verified=True,initial_clear_ms=publication_errors[0]*1000,speed_multiplier=meta['speed_multiplier'],footer=True,offscreen_border_rgb=[0,0,0],source=meta['scope'],title=title,title_costs=title_costs,
                title_cost_method='Guest elapsed inclusive entry to matched PC/SP return, including RET/IRQ. No tracked self costs; cold UI only, never add to active-frame work.',
                scope='Lossless selected boot states on the original timeline, timing/silence, all96 original reveal units shifted8px, full title on/off pixels, optional logo, fixed brackets and blinking numeric masks. Recorded scanout retained; no live gameplay-cycle claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session');a=p.parse_args();verify(a.bundle)
