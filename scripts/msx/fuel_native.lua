-- Externally clocked original fuel component; no arcade foreground/IRQ.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('FUEL_OUTPUT'))
local function load(n) local f=assert(io.open(root..'/'..n,'rb'));local d=f:read('a');f:close();return d end
local cases=load('cases.bin');local seed=load('source-seed.bin')
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,tick,kind,limit,active,wait=0,0,0,0,0,false,0
local function byte(a,v) s:write_u8(a,v) end
local function issue()
 index=index+1;if index>#cases/28 then out:close();m:exit();return end
 local p=(index-1)*28;tick=0;wait=0
 local round,frac,whole,count,mode,clock,enabled,rate
 kind,round,frac,whole,count,mode,clock,enabled,rate=cases:byte(p+1,p+9)
 limit=cases:byte(p+10)+256*cases:byte(p+11)
 for i=1,4096 do byte(0x8000+i-1,seed:byte(i)) end
 for i=0,7 do byte(0x80a0+i,cases:byte(p+12+i));byte(0x8060+i,cases:byte(p+20+i)) end
 byte(0x81b0,round);byte(0x826a,frac);byte(0x826b,whole);byte(0x8271,count)
 byte(0x8020,mode);byte(0x8269,clock);byte(0x828b,enabled);byte(0x826e,rate)
 byte(0x8023,cases:byte(p+28));byte(0x824d,0)
 local code
 if kind==2 then code={0xf3,0xcd,0xa9,0x1f,0x76,0x18,0xfd}
 elseif kind==1 then code={0xf3,0x3a,0x23,0x80,0xcd,0x6b,0x1e,0x76,0x18,0xfd}
 else code={0xf3,0xcd,0xcc,0x1e,0x21,0x69,0x82,0x34,0x21,0x4d,0x82,0x34,0x7e,0xe6,0x3f,0xcc,0x82,0x04,0x76,0x18,0xfd} end
 for i,b in ipairs(code) do byte(0x9f80+i-1,b) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f80
end
local function record(done)
 local result={string.pack('<I2I2',index-1,tick)}
 for _,a in ipairs({0x826a,0x826b,0x8269,0x8020,0x8023,0x8292,0x8289,0x828c,0x828a}) do result[#result+1]=string.char(s:read_u8(a)) end
 for _,range in ipairs({{0x8144,8},{0x80a0,8},{0x8060,8}}) do
  for a=range[1],range[1]+range[2]-1 do result[#result+1]=string.char(s:read_u8(a)) end
 end
 for _,a in ipairs({0x800f,0x81b2,0x82d0,0x8027,0x8028,0x89f4}) do result[#result+1]=string.char(s:read_u8(a)) end
 result[#result+1]=string.char(done and 1 or 0);out:write(table.concat(result))
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then s:write_direct_u8(0x0b2f,0xc9);active=true;issue();return end
 if not active then return end
 local halted=cpu.state['HALT'].value~=0;local pc=cpu.state['PC'].value
 local done=kind~=0 and halted and pc>=0x9f80
 if kind==0 and not halted then wait=wait+1;assert(wait<20,'Consumption did not return');return end
 -- Bonus may be halted at a source HALT or spinning at the five-tick wait.
 record(done or kind==0 and tick==limit-1)
 if done or kind==0 and tick==limit-1 then assert(cpu.state['SP'].value==0x83f0,'Fuel stack imbalance');issue();return end
 tick=tick+1;assert(tick<10000,'Fuel conversion did not finish')
 if kind~=0 then
  byte(0x8269,(s:read_u8(0x8269)+1)%256)
  if halted then cpu.state['HALT'].value=0 end
 else
  cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f80
 end
end)
