-- Original explosion drawing at every fine-scroll phase, then the original
-- non-final-life wait threshold. These are isolated component probes.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local root=assert(os.getenv('DEATH_OUTPUT'))
local fields={}
for _,p in pairs(m.ioport.ports) do for _,f in pairs(p.fields) do fields[f.name]=f end end
local frame,index,wait,phase,tick=0,0,0,'boot',0
local function byte(a,v) s:write_u8(a,v) end
local function save(name,first,n)
 local bytes={}
 for a=first,first+n-1 do bytes[#bytes+1]=string.char(s:read_u8(a)) end
 local f=assert(io.open(root..'/'..name,'wb'));f:write(table.concat(bytes));f:close()
end
local function run(code)
 for i,b in ipairs(code) do byte(0x9f80+i-1,b) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x9ff0;cpu.state['PC'].value=0x9f80
end
local function effect()
 for a=0x8400,0x87ff do byte(a,0x81);byte(a+0x800,0x15) end
 -- DI; original player init; set camera fine phases; IX=player, B=rock path;
 -- CALL original explosion; HALT. No arcade foreground/IRQ is needed.
 run({0xf3,0xcd,0x6c,0x0c,0x3e,index%8,0x32,0x4d,0x80,
      0x3e,math.floor(index/8),0x32,0x4f,0x80,0xdd,0x21,0x68,0x80,
      0x06,0x00,0xcd,0x60,0x19,0x76,0x18,0xfd})
 wait=2
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==1800 then fields['Coin 1']:set_value(1) end
 if frame==1804 then fields['Coin 1']:set_value(0) end
 if frame==1860 then fields['1 Player Start']:set_value(1) end
 if frame==1864 then fields['1 Player Start']:set_value(0) end
 if frame==2200 then phase='effect';effect()
 elseif phase=='effect' then
  wait=wait-1
  if wait==0 then
   assert(cpu.state['HALT'].value~=0,'Original explosion drawing did not return')
   assert(cpu.state['SP'].value==0x9ff0,'Original explosion unbalanced the stack')
   save(string.format('effect-%02d.bin',index),0x8000,4096)
   index=index+1
   if index==64 then
    -- Return only after the original CP $78 wait has completed.
    s:write_direct_u8(0x1930,0xc9)
    byte(0x824b,0);tick=0;phase='timer'
    run({0xf3,0xcd,0x29,0x19,0x76,0x18,0xfd})
   else effect() end
  end
 elseif phase=='timer' then
  if cpu.state['HALT'].value~=0 then
   assert(tick==120,'Original explosion wait returned at the wrong tick')
   local f=assert(io.open(root..'/hold-ticks.txt','w'));f:write(tostring(tick)..'\n');f:close()
   f=assert(io.open(root..'/complete','w'));f:write('ok\n');f:close();m:exit()
  else
   assert(tick<120,'Original explosion wait did not finish')
   tick=tick+1;byte(0x824b,tick)
  end
 end
end)
