-- Controlled original181B collision/1885 rebound fixtures. No ROM writes.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local out=assert(os.getenv('NRX_ENEMY_ROCK_OUTPUT'))
local f=assert(io.open(out..'/vectors.bin','rb'));local vectors=f:read('*a');f:close()
local results=assert(io.open(out..'/results.bin','wb'))
local frame=0;local index=0;local pending=false;local observed=false
local tap=s:install_read_tap(0x1858,0x1858,'enemy_rock_return',function(a,v)
 if pending and not observed and not m:side_effects_disabled() and cpu.state.PC.value==a then
  for at=0x8088,0x80a7 do results:write(string.char(s:read_u8(at))) end
  observed=true;cpu.state.HALT.value=1
 end
end)
emu.register_frame_done(function()
 assert(tap);frame=frame+1;if frame<10 then return end
 if pending then assert(observed,'Original collision fixture did not return') end
 if index*34==#vectors then
  results:close();local done=assert(io.open(out..'/complete','w'));done:write('ok\n');done:close();m:exit();return
 end
 for at=0x8000,0x8fff do s:write_u8(at,0) end
 for at=0x9800,0x9fff do s:write_u8(at,0) end
 s:write_u8(0xa080,0) -- Normal player entry services this watchdog each frame.
 local offset=index*34
 for n=1,32 do s:write_u8(0x8087+n,vectors:byte(offset+n)) end
 local cell=vectors:byte(offset+33)+256*vectors:byte(offset+34)
 s:write_u8(cell,3)
 cpu.state.SP.value=0x8400;cpu.state.IX.value=0x8088;cpu.state.IY.value=0
 cpu.state.BC.value=0x0100;cpu.state.PC.value=0x181b
 cpu.state.IFF1.value=0;cpu.state.IFF2.value=0;cpu.state.HALT.value=0
 index=index+1;pending=true;observed=false
end)
