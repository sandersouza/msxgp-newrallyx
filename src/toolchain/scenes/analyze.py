"""Measured background restrictions and explicitly conservative sprite estimates."""


def analyze(preview, assets):
    width,height=256,212
    rgb_pixels=list(preview.image.get_flattened_data())
    def palette_region(rect):
        indices=set(); colors=set()
        for y in range(rect[1],rect[3]):
            start=y*width
            for x in range(rect[0],rect[2]):
                indices.add(preview.indices[start+x]); colors.add(rgb_pixels[start+x])
        return dict(source_indices=sorted(indices),source_index_count=len(indices),
                    rgb=[list(c) for c in sorted(colors)],rgb_count=len(colors))
    palette=palette_region([0,0,width,height])
    palette['regions']={name:palette_region(segment['destination']) for name,segment in
                        [('maze',preview.transforms['maze']),*preview.transforms['blocks'].items()]}
    palette['scanlines']=[palette_region([0,y,width,y+1]) for y in range(height)]
    violations=[]
    max_colors=0
    for y in range(height):
        for x in range(0,width,8):
            indices=set(preview.background[y*width+x:y*width+x+8])
            colors={tuple(assets.palette['rgb'][i]) for i in indices}
            max_colors=max(max_colors,len(colors))
            if len(colors)>2:
                violations.append(dict(x=x,y=y,indices=sorted(indices)))
    bbox=[0]*height; opaque=[0]*height; entries=[0]*height
    demand=[]; identities=set()
    for obj in preview.objects:
        x0,y0,x1,y1=obj.rect
        w,h=x1-x0,y1-y0
        colors=set(); rows=set()
        for iy in range(h):
            y=y0+iy
            if not 0<=y<height: continue
            if x0<width and x1>0: bbox[y]+=1
            for ix in range(w):
                color=obj.colors[iy*w+ix]
                if color!=255 and 0<=x0+ix<width:
                    colors.add(color); rows.add(y)
        for y in rows: opaque[y]+=1
        if not colors: continue
        identities.add((obj.kind,obj.id))
        # All allocated 16-high entries consume scanline slots, even on blank rows.
        layers=len(colors)
        for y in range(max(0,y0),min(height,y0+16)):
            entries[y]+=layers
        demand.append(dict(kind=obj.kind,id=obj.id,code=obj.code,rect=list(obj.rect),
            colors=sorted(colors),estimated_entries=layers,
            opaque_scanlines=sorted(rows),hardware_height=16))
    result=dict(schema_version=1,palette=palette,
        screen4=dict(pattern_row_width=8,max_colors_per_row=max_colors,
            violating_rows=len(violations),violations=violations,
            assumption='Background only; exact source RGB equality; no palette conversion; 212-line proposal.'),
        screen5=dict(palette_budget=16,required_rgb_colors=palette['rgb_count'],
            fits_palette_budget=palette['rgb_count']<=16,
            assumption='One global 16-color palette; RGB count includes shadows. '
                'V9938 3-bit-channel palette conversion is not performed or certified.'),
        sprites=dict(visible_source_objects=len(identities),estimated_entries=sum(d['estimated_entries'] for d in demand),
            peak_entries_per_scanline=max(entries),hardware_entry_limit=32,scanline_entry_limit=8,
            fits_total_entries=sum(d['estimated_entries'] for d in demand)<=32,
            over_limit_scanlines=[y for y,n in enumerate(entries) if n>8],
            hardware_entries_per_scanline=entries,bounding_box_occupancy=bbox,
            opaque_source_objects_per_scanline=opaque,objects=demand,
            assumption='Conservative fixed-color layers: one 16x16 entry per visible color per placed object; '
                'dots padded to 16x16; blank rows still consume Y slots; wholly invisible objects omitted; '
                'no per-row recoloring or color-combination optimization; transparent source index omitted. '
                'Arcade priority/occlusion may require software or additional splitting.'),
        effects=dict(shadow_pixels=sum(preview.shadow),
            assumption='Dot shadow mixing and smoke/background tiles may require software rendering; '
                'sprite entry counts do not prove faithful reproduction of arithmetic mixing.'))
    if 'compact' in preview.transforms:
        result['radar_projection']=preview.transforms['compact']['radar']
    return result
