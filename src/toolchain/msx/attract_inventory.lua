-- Read-only original attract acquisition; no coin/start or CPU-state writes.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local out=assert(os.getenv('ATTRACT_OUTPUT'))
local frame=0
local function save(name,first,length)
    local f=assert(io.open(out..'/'..name,'wb'))
    for a=first,first+length-1 do f:write(string.char(s:read_u8(a))) end
    f:close()
end
cpu.debug:bpset(0x0c2c,'b@8020==0',
    'save '..string.format('%q',out..'/demo-video.bin')..',8000,1000;'
    ..'save '..string.format('%q',out..'/demo-work.bin')..',9800,800;bpdisable;g')
m.debugger.execution_state='run'
emu.register_frame_done(function()
    frame=frame+1
    if frame%120==0 then
        local name=string.format('frame-%04d',frame)
        save(name..'.video',0x8000,4096)
        assert(m.screens[':screen']:snapshot(out..'/'..name..'.png')==nil)
    end
    local f=io.open(out..'/demo-video.bin','rb')
    if f then
        f:close()
        assert(m.screens[':screen']:snapshot(out..'/demo.png')==nil)
        local complete=assert(io.open(out..'/complete','w'))
        complete:write(frame..'\n');complete:close();m:exit()
    elseif frame>3600 then error('Original attract acquisition timed out') end
end)
