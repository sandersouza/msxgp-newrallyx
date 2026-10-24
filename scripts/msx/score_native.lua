-- Isolated original flag-point/high-score/bonus-life oracle. Source files stay intact.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('SCORE_OUTPUT'))
local function load(n) local f=assert(io.open(root..'/'..n,'rb'));local d=f:read('a');f:close();return d end
local cases=load('cases.bin');local seed=load('source-seed.bin')
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,active,seen,wait=0,0,false,0,0
local function byte(a,v) s:write_u8(a,v) end
local function issue()
 index=index+1;if index>#cases/22 then out:close();m:exit();return end
 wait=0
 local p=(index-1)*22
 local reset,ordinal,kind,mode,awards,lives=cases:byte(p+1,p+6)
 if reset==1 then
  for i=1,4096 do byte(0x8000+i-1,seed:byte(i)) end
  for i=0,7 do byte(0x80a0+i,cases:byte(p+7+i));byte(0x8060+i,cases:byte(p+15+i)) end
  byte(0x8023,mode);byte(0x81b2,awards);byte(0x800f,lives);seen=0
 end
 local code={0xf3}
 local function add(v) code[#code+1]=v end
 local function call(a) add(0xcd);add(a%256);add(math.floor(a/256)) end
 if seen~=ordinal then
  seen=ordinal;byte(0x8250,ordinal);byte(0x8271,ordinal)
  if kind==4 then call(0x1e62) end
  if kind==2 then for _,v in ipairs({0x21,0x23,0x80,0x34}) do add(v) end end
  call(0x1aa4)
 end
 add(0x76);add(0x18);add(0xfd)
 for i,b in ipairs(code) do byte(0x9f80+i-1,b) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f80
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then
  s:write_direct_u8(0x1aca,0xc9);s:write_direct_u8(0x0b2f,0xc9)
  active=true;issue();return
 end
 if not active then return end
 if cpu.state['HALT'].value==0 then
  wait=wait+1;assert(wait<20,'Original score component did not return');return
 end
 assert(cpu.state['SP'].value==0x83f0,'Original score component unbalanced stack')
 local result={}
 for a=0x80a0,0x80a7 do result[#result+1]=string.char(s:read_u8(a)) end
 for a=0x8060,0x8067 do result[#result+1]=string.char(s:read_u8(a)) end
 for _,a in ipairs({0x800f,0x81b2,0x8023,0x82d0,0x8250}) do result[#result+1]=string.char(s:read_u8(a)) end
 result[#result+1]=string.char(seen);out:write(table.concat(result));issue()
end)
