from meta_analyse.flow_style import flow_cell_style

def test_quality_badges_are_distinct():
    assert flow_cell_style(5,"STALE","STALE") != flow_cell_style(5,"UNVERIFIED","UNVERIFIED")
    assert flow_cell_style(5,"PROVISIONAL","PROVISIONAL") != flow_cell_style(5,"STALE","STALE")

def test_delta_color_requires_provisional_quality():
    assert flow_cell_style(3,"100","PROVISIONAL") != flow_cell_style(3,"-100","PROVISIONAL")
    assert flow_cell_style(3,"100","UNVERIFIED") == flow_cell_style(3,"-100","UNVERIFIED")
    assert flow_cell_style(7,"nan","PROVISIONAL") == flow_cell_style(7,"—","PROVISIONAL")
