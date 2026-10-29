-- Real first credit/start; later original initializers use an explicit RAM seed.
-- No ROM patches, altered speed tables, forced motion or muted enemy voices.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local out=assert(os.getenv('NRX_CHALLENGE_SPEED_OUTPUT'))
local fields={};for _,f in pairs(m.ioport.ports[':P1'].fields) do fields[f.mask]=f end
local rounds={2,3,4,8,12,16};local case=1;local frame=0;local age=0
local initialized=false;local observing=false;local seed=nil
local rows=assert(io.open(out..'/frames.tsv','w'))
local function bytes(first,count)
 local b={};for a=first,first+count-1 do b[#b+1]=string.char(s:read_u8(a)) end;return table.concat(b)
end
local function save(name,data) local f=assert(io.open(out..'/'..name,'wb'));f:write(data);f:close() end
local tap=s:install_read_tap(0x0c2c,0x0c2c,'challenge_ready',function(a,v)
 if not m:side_effects_disabled() and cpu.state.PC.value==a and s:read_u8(0x8020)==2 then initialized=true end
end)
emu.register_frame_done(function()
 assert(tap);frame=frame+1
 if frame==1800 then fields[128]:set_value(1) end
 if frame==1804 then fields[128]:set_value(0) end
 if frame==1860 then fields[64]:set_value(1) end
 if frame==1864 then fields[64]:set_value(0) end
 if initialized and not observing then
  local data=bytes(0x8000,4096)
  assert(s:read_u8(0x81b0)==rounds[case],'Original initializer returned wrong round')
  seed=seed or data;save('round-'..rounds[case]..'.bin',data)
  observing=true;age=0
 end
 if observing then
  local r={rounds[case],age,frame}
  for _,a in ipairs({0x8020,0x8025,0x8026,0x8027,0x8028,0x8029,0x802a,0x802d,0x802e,0x8069,0x806a,0x826b}) do r[#r+1]=s:read_u8(a) end
  rows:write(table.concat(r,' ')..'\n');age=age+1
  if age==32 then
   case=case+1
   if case>#rounds then rows:close();save('complete','ok\n');m:exit();return end
   for i=1,#seed do s:write_u8(0x8000+i-1,seed:byte(i)) end
   s:write_u8(0x81b0,rounds[case]-1);s:write_u8(0x8000,1);s:write_u8(0x8001,0);s:write_u8(0x89f5,1)
   cpu.state.HALT.value=0;cpu.state.SP.value=0x8400;cpu.state.PC.value=0x08bf
   cpu.state.IFF1.value=1;cpu.state.IFF2.value=1
   observing=false;initialized=false
  end
 end
 if frame==12000 then error('Original challenge speed capture timeout') end
end)
