-- Original sound routine and analog BANG fixtures. No original ROM writes.
local m = manager.machine
local cpu = m.devices[':maincpu']
local s = cpu.spaces['program']
local out = assert(os.getenv('NRX_ARCADE_AUDIO_OUTPUT'))
local function read(path) local f=assert(io.open(path,'rb'));local b=f:read('a');f:close();return b end
local seed=read(out..'/seed.bin')
local rows=assert(io.open(out..'/wsg.tsv','w'))
local parts=assert(io.open(out..'/parts.tsv','w'))
local shadow={};for i=0,31 do shadow[i]=0 end
local frame=0
local stage='crash'
local stage_frame=0
local taps={}
local events=assert(io.open(out..'/events.tsv','w'))
taps[1]=s:install_write_tap(0xa100,0xa11f,'feedback_wsg',function(a,v)
 if not m:side_effects_disabled() then shadow[a-0xa100]=v&15 end
end)
taps[2]=s:install_read_tap(0x2b58,0x2b87,'feedback_parts',function(a,v)
 if frame>=480 and not m:side_effects_disabled() and a%2==0 then
  parts:write(string.format('%s %d %d %d\n',stage,stage_frame,(a-0x2b58)//2,cpu.state.PC.value))
 end
end)
taps[3]=s:install_write_tap(0xa180,0xa180,'feedback_bang',function(a,v)
 if not m:side_effects_disabled() then events:write(string.format('%d %s %d %d\n',frame,tostring(m.time),cpu.state.PC.value,v)) end
end)
emu.register_frame_done(function()
 assert(#taps==3) -- Retain tap userdata across Lua garbage collection.
 frame=frame+1;s:write_u8(0xa080,0)
 if frame==120 then
  for i=1,#seed do s:write_u8(0x8000+i-1,seed:byte(i)) end
  for a=0x8a00,0x8bff do s:write_u8(a,0) end
  s:write_u8(0xa182,1);s:write_u8(0x89f4,128);s:write_u8(0x89f5,8);s:write_u8(0x89f6,0)
  for i,v in ipairs({0xf3,0xcd,0x80,0x25,0x76,0x18,0xfd}) do s:write_u8(0x9f00+i-1,v) end
 end
 if frame==480 then
  stage='intro';stage_frame=0
  for i=1,#seed do s:write_u8(0x8000+i-1,seed:byte(i)) end
  for a=0x8a00,0x8bff do s:write_u8(a,0) end
  s:write_u8(0x81b0,4);s:write_u8(0x8020,2);s:write_u8(0x8021,1)
  s:write_u8(0x89f4,0);s:write_u8(0x89f5,64);s:write_u8(0x89f6,0)
  for i,v in ipairs({0xf3,0xcd,0x80,0x25,0x76,0x18,0xfd}) do s:write_u8(0x9f00+i-1,v) end
 end
 if frame>=120 then
  if frame~=120 and frame~=480 then
   stage_frame=stage_frame+1
   local r={stage,stage_frame,s:read_u8(0x89f5)}
   for i=0,31 do r[#r+1]=shadow[i] end
   rows:write(table.concat(r,' ')..'\n')
   if stage=='intro' and (s:read_u8(0x89f5)&64)==0 then
    stage='music';stage_frame=0
    for a=0x8a00,0x8bff do s:write_u8(a,0) end
    s:write_u8(0x89f5,16)
   end
  end
  cpu.state.HALT.value=0;cpu.state.IFF1.value=0;cpu.state.IFF2.value=0
  cpu.state.SP.value=0x9ff0;cpu.state.PC.value=0x9f00
 end
 if stage=='music' and stage_frame==1800 or frame==4000 then
  rows:close();parts:close();events:close();local f=assert(io.open(out..'/complete','w'));f:write('ok\n');f:close();m:exit()
 end
end)
