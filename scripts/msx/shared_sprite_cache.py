"""Reference policy for twelve complete-mask slots and seven visible cars."""


def assign(keys,front,requests):
    if len(keys)!=12 or len(requests)>7 or len(front)>7:
        raise ValueError('Invalid complete-car cache population')
    keys=list(keys);reserved={keys.index(key) for key in requests if key in keys}
    slots=[];dirty=set()
    for key in requests:
        if key in keys:slot=keys.index(key)
        else:
            free=[i for i in range(12) if i not in reserved]
            slot=next((i for i in free if i not in front),free[0])
            keys[slot]=key;dirty.add(slot)
        reserved.add(slot);slots.append(slot)
    return dict(keys=keys,slots=slots,dirty=dirty,preload=dirty-set(front),
        vblank=dirty&set(front))
