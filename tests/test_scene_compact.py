"""Synthetic HUD fragments and radar markers; no original game pixels."""
import copy
import unittest
from PIL import Image
from src.toolchain.scenes.layout import compose
from src.toolchain.scenes.render import Frame, Object
from test_scene_render import scene


def synthetic_hud():
    assets,capture,_=scene()
    indices=bytearray(288*224)
    def fill(rect,color):
        for y in range(rect[1],rect[3]):
            for x in range(rect[0],rect[2]): indices[y*288+x]=color
    for i in range(8): fill([224+i*8,0,232+i*8,8],i+1)
    fill([240,8,288,16],9) # score fits six cells, including the rightmost digit
    fill([224,16,248,24],10)
    fill([272,24,288,32],11)
    fill([240,56,272,61],12)
    fill([226,65,286,71],14) # full 60-pixel fuel gauge
    fill([224,80,288,192],13)
    fill([281,90,283,92],3) # 2x2 tile-layer radar flag
    fill([224,192,248,200],6)
    fill([224,208,264,216],7); fill([280,208,288,216],7)
    image=Image.new('RGB',(288,224))
    image.putdata([tuple(assets.palette['rgb'][i]) for i in indices])
    frame=Frame(image,bytes(indices),bytes(indices),bytes(288*224),bytes(288*224),[])
    return assets,capture,frame


class CompactTests(unittest.TestCase):
    def test_200_pixel_maze_and_unscaled_hiscore_fragments(self):
        assets,capture,frame=synthetic_hud()
        before=copy.deepcopy(capture.state)
        pixels_before=(frame.image.tobytes(),frame.indices,frame.background,frame.shadow,capture.video,capture.radar)
        preview=compose(frame,capture,assets)
        self.assertEqual(preview.image.size,(256,212))
        self.assertEqual(preview.transforms['maze'],dict(source=[12,6,212,218],destination=[0,0,200,212]))
        self.assertEqual(preview.image.crop((200,0,216,8)).tobytes(),frame.image.crop((224,0,240,8)).tobytes())
        self.assertEqual(preview.image.crop((216,0,256,8)).tobytes(),frame.image.crop((248,0,288,8)).tobytes())
        self.assertEqual(preview.image.crop((200,8,256,16)).tobytes(),frame.image.crop((232,8,288,16)).tobytes())
        self.assertEqual(preview.transforms['compact']['title'],'HISCORE')
        self.assertEqual(capture.state,before)
        self.assertEqual((frame.image.tobytes(),frame.indices,frame.background,frame.shadow,capture.video,capture.radar),pixels_before)
        self.assertEqual(preview.image.crop((200,196,240,212)).tobytes(),frame.image.crop((224,208,264,224)).tobytes())
        self.assertEqual(preview.image.crop((240,196,256,212)).tobytes(),frame.image.crop((272,208,288,224)).tobytes())

    def test_flags_and_mobile_dots_keep_dimensions_at_projected_positions(self):
        assets,capture,frame=synthetic_hud()
        dots=bytearray(assets.pixels['dots']); dots[:16]=bytes([2]*16)
        assets.pixels['dots']=bytes(dots)
        # A complete 4x4 marker at the source's right edge must remain complete.
        frame.objects=[Object('dot',20,0,(284,140,288,144),bytes([18]*16))]
        preview=compose(frame,capture,assets)
        obj=next(o for o in preview.objects if o.kind=='dot')
        self.assertEqual(obj.rect,(252,124,256,128))
        self.assertEqual(obj.colors,bytes([18]*16))
        self.assertEqual(sum(i==3 for i in preview.background),4)
        self.assertEqual(sum(i==18 for i in preview.indices),16)
        self.assertEqual(preview.image.getpixel((252,124)),(75,75,75))
        self.assertEqual(preview.transforms['compact']['radar']['clipped_markers'],[])

    def test_projection_collision_is_reported_and_uses_object_order(self):
        assets,capture,frame=synthetic_hud()
        dots=bytearray(assets.pixels['dots']); dots[:16]=bytes([1]*16); dots[16:32]=bytes([2]*16)
        assets.pixels['dots']=bytes(dots)
        frame.objects=[Object('dot',20,0,(240,140,244,144),bytes([17]*16)),
                       Object('dot',21,1,(244,140,248,144),bytes([18]*16))]
        preview=compose(frame,capture,assets)
        radar=preview.transforms['compact']['radar']
        self.assertEqual(radar['source_mobile_overlap_pixels'],0)
        self.assertGreater(radar['projected_mobile_overlap_pixels'],0)
        self.assertTrue(radar['new_mobile_overlap_pairs'])
        # Later hardware dot wins in the overlap, without shrinking either marker.
        self.assertEqual(preview.indices[124*256+217],18)
        from src.toolchain.scenes.analyze import analyze
        report=analyze(preview,assets)
        self.assertEqual(report['radar_projection']['projected_mobile_overlap_pixels'],
                         radar['projected_mobile_overlap_pixels'])

    def test_transparent_dot_pixels_preserve_flags_and_do_not_count_as_overlap(self):
        assets,capture,frame=synthetic_hud()
        dots=bytearray(assets.pixels['dots']); dots[:16]=bytes([3]*16); dots[6]=2
        assets.pixels['dots']=bytes(dots)
        colors=bytearray([255]*16); colors[6]=18
        frame.objects=[Object('dot',20,0,(280,89,284,93),bytes(colors))]
        preview=compose(frame,capture,assets)
        self.assertEqual(preview.indices[74*256+250],3) # transparent pixel leaves flag ink
        self.assertEqual(preview.image.getpixel((250,74)),(21,21,21))
        self.assertEqual(preview.indices[74*256+251],18)
        self.assertEqual(preview.image.getpixel((251,74)),(75,75,75))
        self.assertEqual(preview.indices[73*256+249],13) # transparent pixel leaves backdrop
        radar=preview.transforms['compact']['radar']
        self.assertEqual(radar['source_overlap_pixels'],1)
        self.assertEqual(radar['projected_overlap_pixels'],1)
        self.assertEqual(radar['new_overlap_pairs'],[])

    def test_fuel_fraction_is_preserved_with_a_52_pixel_inner_gauge(self):
        assets,capture,frame=synthetic_hud()
        full=compose(frame,capture,assets)
        self.assertEqual(full.indices[49*256+200:49*256+256].count(14),52)
        indices=bytearray(frame.indices)
        for y in range(65,71):
            for x in range(226,256): indices[y*288+x]=0
        frame.indices=frame.background=bytes(indices)
        frame.image.putdata([tuple(assets.palette['rgb'][i]) for i in indices])
        preview=compose(frame,capture,assets)
        row=preview.indices[49*256+200:49*256+256]
        self.assertEqual(row.count(14),26)
        self.assertEqual(preview.transforms['compact']['fuel']['source_inner_width'],60)
        self.assertEqual(preview.transforms['compact']['fuel']['destination_inner_width'],52)
        for y in range(65,71):
            for x in range(256,286): indices[y*288+x]=0
        frame.indices=frame.background=bytes(indices)
        frame.image.putdata([tuple(assets.palette['rgb'][i]) for i in indices])
        empty=compose(frame,capture,assets)
        self.assertEqual(empty.indices[49*256+200:49*256+256].count(14),0)

    def test_nonblank_trimmed_information_and_flipped_captures_are_rejected(self):
        assets,capture,frame=synthetic_hud()
        capture.state['registers']['flip']=True
        with self.assertRaisesRegex(ValueError,'upright'): compose(frame,capture,assets)
        capture.state['registers']['flip']=False
        frame.image.putpixel((287,192),(255,0,0))
        with self.assertRaisesRegex(ValueError,'lives'):
            compose(frame,capture,assets)
