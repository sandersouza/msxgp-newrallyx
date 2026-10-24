-- Unmodified original two-player lifecycle, driven only through input ports.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local out=assert(os.getenv('SESSION_INVENTORY_OUTPUT'))
local fields={}
for _,port in pairs(m.ioport.ports) do
    for _,field in pairs(port.fields) do fields[field.name]=field end
end
local events=assert(io.open(out..'/events.tsv','w'))
local frame,previous,turns,checks=0,0,0,0
local function word(at) return s:read_u8(at)+256*s:read_u8(at+1) end
local function save(name)
    local f=assert(io.open(out..'/'..name,'wb'))
    for at=0x8000,0x8fff do f:write(string.char(s:read_u8(at))) end
    f:close()
end
m.debugger.execution_state='run'
emu.register_frame_done(function()
    frame=frame+1
    if frame==1750 or frame==1810 then fields['2 Players Start']:set_value(1) end
    if frame==1754 or frame==1814 then fields['2 Players Start']:set_value(0) end
    if frame==1758 or frame==1818 then
        assert(s:read_u8(0x8020)~=2,'Original accepted two-player start without two credits')
        assert(s:read_u8(0x8024)==(frame==1818 and 1 or 0),'Rejected start consumed a credit')
        checks=checks+1
    end
    if frame==1800 or frame==1820 then fields['Coin 1']:set_value(1) end
    if frame==1804 or frame==1824 then fields['Coin 1']:set_value(0) end
    if frame==1860 then fields['2 Players Start']:set_value(1) end
    if frame==1864 then fields['2 Players Start']:set_value(0) end
    if frame>=1864 then
        local pointer=word(0x8988)
        local phase=word(0x899c)
        if s:read_u8(0x8020)==2 and s:read_u8(0x8021)>0 and
           (pointer==0x800f or pointer==0x8010) and phase>=0x8000 and phase<0x9000 and
           s:read_u8(phase)==1 and pointer~=previous then
            turns=turns+1;previous=pointer
            events:write(string.format('%d %d %d %d %d %d %d %d\n',frame,pointer-0x800f,
                s:read_u8(0x800f),s:read_u8(0x8010),s:read_u8(0x81b0),
                s:read_u8(0x81b1),s:read_u8(0x8024),s:read_u8(0x8021)))
            events:flush();save(string.format('turn-%d.bin',turns))
            if turns==1 then m.screens[':screen']:snapshot(out..'/two-player.png') end
        end
        if turns>0 and s:read_u8(0x800f)==0 and s:read_u8(0x8010)==0 then
            assert(checks==2,'Missing original rejected-start checks')
            save('game-over.bin');events:close()
            local f=assert(io.open(out..'/complete','w'));f:write(frame..'\n');f:close()
            m:exit();return
        end
    end
    if frame>40000 then error('Original natural two-player session timed out') end
end)
