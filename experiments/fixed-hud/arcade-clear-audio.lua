-- Isolated original clear-cue request, one unmodified2580 call per video tick.
-- RAM fixture only; no ROM writes, downloads or forced score/note output.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local out=assert(os.getenv('NRX_CLEAR_AUDIO_OUTPUT'));local f=assert(io.open(out..'/seed.bin','rb'));local seed=f:read('a');f:close()
local rows=assert(io.open(out..'/wsg.tsv','w'));local frame=0;local tick=0;local finished=nil;local shadow={}
for i=0,31 do shadow[i]=0 end
local tap=s:install_write_tap(0xa100,0xa11f,'clear_wsg',function(a,v)
 if not m:side_effects_disabled() then shadow[a-0xa100]=v&15 end
end)
emu.register_frame_done(function()
 assert(tap);frame=frame+1;s:write_u8(0xa080,0)
 if frame==120 then
  for i=1,#seed do s:write_u8(0x8000+i-1,seed:byte(i)) end
  for a=0x8a00,0x8bff do s:write_u8(a,0) end
  s:write_u8(0xa182,1);s:write_u8(0x8020,3)
  s:write_u8(0x89f4,0);s:write_u8(0x89f5,0x28);s:write_u8(0x89f6,0)
  for i,v in ipairs({0xf3,0xcd,0x80,0x25,0x76,0x18,0xfd}) do s:write_u8(0x9f00+i-1,v) end
 end
 if frame>120 then
  tick=tick+1;local request=s:read_u8(0x89f5);local r={tick,request}
  for i=0,31 do r[#r+1]=shadow[i] end
  rows:write(table.concat(r,' ')..'\n')
  if not finished and request&32==0 then finished=tick end
  if finished and tick>=finished+4 then
   rows:close();local f=assert(io.open(out..'/complete','w'));f:write(tostring(finished));f:close();m:exit();return
  end
 end
 if frame>=120 then
  cpu.state.HALT.value=0;cpu.state.IFF1.value=0;cpu.state.IFF2.value=0
  cpu.state.SP.value=0x9ff0;cpu.state.PC.value=0x9f00
 end
 if frame==500 then error('Original clear cue did not complete') end
end)
