-- Original single-player decrement/waits/restart prefix; externally clocked.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('LIVES_OUTPUT'))
local function load(n) local f=assert(io.open(root..'/'..n,'rb'));local d=f:read('a');f:close();return d end
local cases=load('cases.bin');local seed=load('source-seed.bin')
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,tick,phase=0,0,0,'boot'
local function byte(a,v) s:write_u8(a,v) end
local function run(code)
 for i,b in ipairs(code) do byte(0x9f80+i-1,b) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f80
end
local function issue()
 index=index+1;if index>#cases/5 then out:close();m:exit();return end
 local p=(index-1)*5;local lives,ordinal,count,frac,whole=cases:byte(p+1,p+5)
 for i=1,4096 do byte(0x8000+i-1,seed:byte(i)) end
 byte(0x800f,lives);byte(0x8250,ordinal);byte(0x8271,count);byte(0x826a,frac);byte(0x826b,whole)
 byte(0x8023,1);byte(0x8020,3);byte(0x8292,1);byte(0x8289,0xc7)
 tick=0;phase='loss';run({0xf3,0xcd,0xda,0x18,0x76,0x18,0xfd})
end
local function record()
 local result={string.pack('<I2I2',index-1,tick)}
 for _,a in ipairs({0x800f,0x8020,0x8250,0x8271,0x8023,0x826a,0x826b,0x8292,0x8289,0x828b,0x81b2,0x82d0}) do result[#result+1]=string.char(s:read_u8(a)) end
 for _,range in ipairs({{0x8025,8},{0x80a0,8},{0x8060,8},{0x8068,24}}) do
  for a=range[1],range[1]+range[2]-1 do result[#result+1]=string.char(s:read_u8(a)) end
 end
 out:write(table.concat(result));issue()
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then
  for _,a in ipairs({0x18e8,0x1bcd,0x073d,0x0908,0x1930,0x1bd8,0x1aca,0x0b2f}) do s:write_direct_u8(a,0xc9) end
  issue();return
 end
 if phase=='boot' then return end
 local halted=cpu.state['HALT'].value~=0
 if phase=='loss' and halted then
  if s:read_u8(0x800f)==0 then byte(0x824b,0xa0);run({0xf3,0xcd,0xd2,0x1b,0x76,0x18,0xfd})
  else byte(0x824b,0);run({0xf3,0xcd,0x29,0x19,0x76,0x18,0xfd}) end
  phase='wait';return
 end
 if phase=='wait' then
  if not halted then tick=tick+1;assert(tick<=120,'Original life wait did not return');byte(0x824b,(s:read_u8(0x824b)+1)%256);return end
  if s:read_u8(0x800f)==0 then record();return end
  -- Same explicit active-driving phase as the accepted selective baseline.
  for i=0,7 do byte(0x8025+i,seed:byte(0x26+i)) end
  run({0xf3,0xcd,0xe7,0x08,0xcd,0x6c,0x0c,0x3e,1,0x32,0x8b,0x82,0x32,0x20,0x80,
       0xaf,0x32,0xd0,0x82,0x2a,0x27,0x80,0x22,0x69,0x80,0x22,0x2d,0x80,
       0x21,0x50,0x82,0x34,0x21,0x71,0x82,0x34,0xcd,0xa4,0x1a,0x76,0x18,0xfd})
  phase='restart';return
 end
 if phase=='restart' and halted then assert(cpu.state['SP'].value==0x83f0,'Original life stack imbalance');record() end
end)
