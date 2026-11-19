-- Controlled original-ROM initializer/board expansion. Explicit RAM seeds and
-- PC/SP/IFF setup; distinct from the real-input natural-session observer.
-- No original ROM bytes are patched; calls execute original08BF/08E7 code.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local out=assert(os.getenv('NRX42_OUTPUT'))
local input=assert(io.open(assert(os.getenv('NRX42_SEED')),'rb'))
local seed=input:read('*a');input:close();assert(#seed==4096)
local frame=0;local index=0;local phase='wait';local taps={}
local snapshots=assert(io.open(out..'/states.bin','wb'))
local boards=assert(io.open(out..'/boards.bin','wb'))
local rows=assert(io.open(out..'/cases.tsv','w'))
rows:write('round\tseed\tlayout\trng_after\trocks\n')
local seeds={1,0x1234}
local function word(a) return s:read_u8(a)+256*s:read_u8(a+1) end
local function bytes(a,n)
 local b={};for i=0,n-1 do b[#b+1]=string.char(s:read_u8(a+i)) end
 return table.concat(b)
end
local function stop() cpu.state.HALT.value=1 end
taps[1]=s:install_read_tap(0x08d4,0x08d4,'nrx42_matrix_prepared',function(a,v)
 if phase=='prepare' and not m:side_effects_disabled() and cpu.state.PC.value==a then
  snapshots:write(bytes(0x8000,4096));snapshots:flush()
  rows:write(table.concat({2+math.floor((index-1)/2),seeds[1+(index-1)%2],
    s:read_u8(0x828f),word(0x8000),s:read_u8(0x8251)},'\t')..'\n');rows:flush()
  phase='expand_next';stop()
 end
end)
taps[2]=s:install_read_tap(0x0952,0x0952,'nrx42_matrix_board',function(a,v)
 if phase=='expand' and not m:side_effects_disabled() and cpu.state.PC.value==a then
  boards:write(bytes(0x9800,1792));boards:flush();phase='next';stop()
 end
end)
local function execute(pc)
 cpu.state.IFF1.value=0;cpu.state.IFF2.value=0
 cpu.state.SP.value=0x9ff0;cpu.state.PC.value=pc;cpu.state.HALT.value=0
end
emu.register_frame_done(function()
 assert(#taps==2);frame=frame+1;s:write_u8(0xa080,0)
 if frame<10 then return end
 if phase=='expand_next' then phase='expand';execute(0x08e7);return end
 if phase=='wait' or phase=='next' then
  index=index+1
  if index>64 then
   rows:close();snapshots:close();boards:close()
   local f=assert(io.open(out..'/complete','w'));f:write('ok\n');f:close();m:exit();return
  end
  for i=1,#seed do s:write_u8(0x8000+i-1,seed:byte(i)) end
  local state=seeds[1+(index-1)%2]
  s:write_u8(0x8000,state%256);s:write_u8(0x8001,math.floor(state/256))
  s:write_u8(word(0x898a),1+math.floor((index-1)/2))
  s:write_u8(0x8292,0);phase='prepare';execute(0x08bf)
 end
 if frame>12000 then print(string.format('Matrix timeout phase=%s case=%d PC=%04x SP=%04x IFF=%d',phase,index,cpu.state.PC.value,cpu.state.SP.value,cpu.state.IFF1.value));m:exit() end
end)
