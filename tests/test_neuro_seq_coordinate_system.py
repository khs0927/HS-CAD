from neuro_seq_cad.io.coordinate_system import cad_to_image_point, image_bbox_to_cad_bbox, image_to_cad_point


def test_image_to_cad_point_flips_y_axis():
    assert image_to_cad_point((10, 20), image_height=100, scale=2) == (20, 160)


def test_cad_to_image_point_reverses_conversion():
    image = (125, 456)
    cad = image_to_cad_point(image, image_height=1000, scale=0.5)
    assert cad_to_image_point(cad, image_height=1000, scale=0.5) == image


def test_image_bbox_to_cad_bbox():
    assert image_bbox_to_cad_bbox([10, 20, 30, 50], image_height=100, scale=1) == (10, 50, 30, 80)

