-- Isolate the contributor arcade cartridge's analog BANG circuit.
-- Halt the original CPU, clear WSG voices, and gate two bounded explosions.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local out=assert(os.getenv('NRX_BANG_OUTPUT'))
local f=assert(io.open(out..'/events.tsv','w'))
local frame=0
emu.register_frame_done(function()
 frame=frame+1
 s:write_u8(0xa080,0)
 if frame>=120 then
  cpu.state.IFF1.value=0;cpu.state.IFF2.value=0;cpu.state.HALT.value=1
  for a=0xa100,0xa11f do s:write_u8(a,0) end
  local gate=(frame>=120 and frame<150) or (frame>=180 and frame<210)
  s:write_u8(0xa180,gate and 1 or 0)
  f:write(string.format('%d %s %d\n',frame,tostring(m.time),gate and 1 or 0))
 end
 if frame==240 then
  f:close();local p=assert(io.open(out..'/complete','w'));p:write('done\n');p:close();m:exit()
 end
end)
