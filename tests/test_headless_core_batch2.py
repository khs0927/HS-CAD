import pytest
from pydantic import ValidationError

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch2 import (
    DetachedTextSpec,
    DimensionOverrideDetachItem,
    DimensionOverrideDetachRequest,
    DimensionTextSnapshot,
    DivideDimensionRequest,
    ExistingStylePolicy,
    JoinDimensionRequest,
    LinearDimensionSnapshot,
    SectionMarkMode,
    SectionMarkRequest,
    SectionNormalSide,
    SourcePolicy,
    TableStyleAction,
    TableStyleRequest,
    TableStyleSnapshot,
    TableStyleSpec,
    execute_dimension_override_detach,
    execute_divide_dimension,
    execute_join_dimensions,
    execute_section_mark,
    execute_table_style,
    plan_dimension_override_detach,
    plan_divide_dimension,
    plan_join_dimensions,
    plan_section_mark,
    plan_table_style,
)


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def dim(handle, x1, x2, *, override="", style="DIM", layer="D-DIM"):
    return LinearDimensionSnapshot(
        handle=handle,
        extension_start=Point3D(x=x1, y=0),
        extension_end=Point3D(x=x2, y=0),
        dimension_line_point=Point3D(x=0, y=2),
        style_name=style,
        layer=layer,
        text_override=override,
    )


class FakeAdapter:
    def __init__(self):
        self.document = "doc-1"
        self.events = []
        self.dimensions = {"D1": dim("D1", 0, 6), "D2": dim("D2", 6, 10)}
        self.text_dimensions = {
            "T1": DimensionTextSnapshot(
                handle="T1",
                current_override="<>\\XNOTE",
                layer="D-DIM",
                text_style="Standard",
                text_height=2.5,
            )
        }
        self.style = TableStyleSnapshot(exists=False)
        self.serial = 0

    def active_document_id(self):
        return self.document

    def begin_undo_mark(self):
        self.events.append("begin")

    def end_undo_mark(self):
        self.events.append("end")

    def read_dimensions(self, handles):
        return [self.text_dimensions[h] for h in handles]

    def set_dimension_override(self, handle, value):
        self.events.append(("override", handle, value))

    def create_text(self, spec: DetachedTextSpec):
        self.events.append(("text", spec.text, spec.layer))
        return "TXT1"

    def read_linear_dimension(self, handle):
        return self.dimensions[handle]

    def read_linear_dimensions(self, handles):
        return [self.dimensions[h] for h in handles]

    def create_linear_dimension(self, spec):
        self.serial += 1
        handle = f"N{self.serial}"
        self.events.append(("dim", handle, spec.extension_start.x, spec.extension_end.x))
        return handle

    def erase_entities(self, handles):
        self.events.append(("erase", tuple(handles)))

    def create_lines(self, specs):
        result = tuple(f"L{i}" for i in range(1, len(specs) + 1))
        self.events.append(("lines", len(specs)))
        return result

    def create_texts(self, specs):
        result = tuple(f"S{i}" for i in range(1, len(specs) + 1))
        self.events.append(("texts", len(specs)))
        return result

    def read_table_style(self, style_name):
        return self.style

    def create_table_style(self, spec):
        self.events.append(("style-create", spec.style_name))

    def update_table_style(self, spec):
        self.events.append(("style-update", spec.style_name))


def table_spec(**overrides):
    values = dict(
        style_name="XI_TB_N",
        title_text_style="Standard",
        header_text_style="Standard",
        data_text_style="Standard",
        title_text_height=4.0,
        header_text_height=3.0,
        data_text_height=2.5,
        horizontal_cell_margin=1.0,
        vertical_cell_margin=0.5,
        flow_direction="down",
    )
    values.update(overrides)
    return TableStyleSpec(**values)


def test_dtd_requires_explicit_text_and_replacement_override():
    with pytest.raises(ValidationError):
        DimensionOverrideDetachItem(
            dimension_handle="T1",
            expected_current_override="<>\\XNOTE",
            insertion_point=Point3D(x=0, y=0),
        )


def test_dtd_rejects_stale_dimension_override():
    request = DimensionOverrideDetachRequest(
        document_id="doc-1",
        items=(
            DimensionOverrideDetachItem(
                dimension_handle="T1",
                expected_current_override="OLD",
                replacement_override="<>",
                detached_text="NOTE",
                insertion_point=Point3D(x=0, y=0),
            ),
        ),
    )
    with pytest.raises(ValueError, match="changed"):
        plan_dimension_override_detach(request, list(FakeAdapter().text_dimensions.values()))


def test_dtd_execution_updates_dimension_and_creates_text_in_one_undo_mark():
    adapter = FakeAdapter()
    request = DimensionOverrideDetachRequest(
        document_id="doc-1",
        items=(
            DimensionOverrideDetachItem(
                dimension_handle="T1",
                expected_current_override="<>\\XNOTE",
                replacement_override="<>",
                detached_text="NOTE",
                insertion_point=Point3D(x=1, y=2),
            ),
        ),
        dry_run=False,
        approval=approved(),
    )
    result = execute_dimension_override_detach(request, adapter)
    assert result.created_text_handles == ("TXT1",)
    assert result.changed_dimension_handles == ("T1",)
    assert adapter.events == [
        "begin",
        ("override", "T1", "<>"),
        ("text", "NOTE", "D-DIM"),
        "end",
    ]


def test_dvd_divides_dimension_into_equal_segments():
    request = DivideDimensionRequest(
        document_id="doc-1",
        source_handle="D1",
        divisions=3,
        source_policy=SourcePolicy.PRESERVE,
    )
    plan = plan_divide_dimension(request, dim("D1", 0, 6))
    assert [(s.extension_start.x, s.extension_end.x) for s in plan.output_dimensions] == [
        (0.0, 2.0),
        (2.0, 4.0),
        (4.0, 6.0),
    ]
    assert plan.dialog_required is False


def test_dvd_rejects_text_override_without_opt_in():
    request = DivideDimensionRequest(
        document_id="doc-1",
        source_handle="D1",
        divisions=2,
        source_policy=SourcePolicy.PRESERVE,
    )
    with pytest.raises(ValueError, match="text override"):
        plan_divide_dimension(request, dim("D1", 0, 6, override="CUSTOM"))


def test_dvd_replace_executes_inside_one_undo_mark():
    adapter = FakeAdapter()
    result = execute_divide_dimension(
        DivideDimensionRequest(
            document_id="doc-1",
            source_handle="D1",
            divisions=3,
            source_policy=SourcePolicy.REPLACE,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.created_handles == ("N1", "N2", "N3")
    assert result.erased_source_handle == "D1"
    assert adapter.events[0] == "begin"
    assert adapter.events[-2:] == [("erase", ("D1",)), "end"]


def test_jd_joins_contiguous_collinear_dimensions():
    request = JoinDimensionRequest(
        document_id="doc-1",
        source_handles=("D2", "D1"),
        source_policy=SourcePolicy.REPLACE,
    )
    plan = plan_join_dimensions(request, [dim("D2", 6, 10), dim("D1", 0, 6)])
    assert plan.source_handles == ("D1", "D2")
    assert plan.output_dimension.extension_start.x == 0
    assert plan.output_dimension.extension_end.x == 10
    assert plan.gaps_detected == ()


def test_jd_rejects_gap_unless_explicitly_allowed():
    request = JoinDimensionRequest(
        document_id="doc-1",
        source_handles=("D1", "D2"),
        source_policy=SourcePolicy.PRESERVE,
    )
    with pytest.raises(ValueError, match="gaps"):
        plan_join_dimensions(request, [dim("D1", 0, 4), dim("D2", 5, 10)])


def test_jd_rejects_mixed_dimension_styles():
    request = JoinDimensionRequest(
        document_id="doc-1",
        source_handles=("D1", "D2"),
        source_policy=SourcePolicy.PRESERVE,
    )
    with pytest.raises(ValueError, match="same style"):
        plan_join_dimensions(request, [dim("D1", 0, 4), dim("D2", 4, 10, style="OTHER")])


def test_jd_execution_creates_one_and_erases_sources():
    adapter = FakeAdapter()
    result = execute_join_dimensions(
        JoinDimensionRequest(
            document_id="doc-1",
            source_handles=("D1", "D2"),
            source_policy=SourcePolicy.REPLACE,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.created_handle == "N1"
    assert result.erased_source_handles == ("D1", "D2")
    assert adapter.events == [
        "begin",
        ("dim", "N1", 0.0, 10.0),
        ("erase", ("D1", "D2")),
        "end",
    ]


def test_scc_generates_one_cut_line_and_two_labels():
    plan = plan_section_mark(
        SectionMarkRequest(
            document_id="doc-1",
            mode=SectionMarkMode.SINGLE,
            cut_start=Point3D(x=0, y=0),
            cut_end=Point3D(x=10, y=0),
            normal_side=SectionNormalSide.LEFT,
            label_start="A",
            label_end="A",
            tail_length=2,
            text_offset=1,
            layer="A-ANNO",
            text_style="Standard",
            text_height=2.5,
        )
    )
    assert plan.command_alias == "SCC"
    assert len(plan.cut_lines) == 1
    assert len(plan.tail_lines) == 2
    assert len(plan.labels) == 2
    assert plan.labels[0].insertion_point.y == 3


def test_scd_requires_explicit_double_line_gap():
    with pytest.raises(ValueError, match="double_line_gap"):
        SectionMarkRequest(
            document_id="doc-1",
            mode=SectionMarkMode.DOUBLE,
            cut_start=Point3D(x=0, y=0),
            cut_end=Point3D(x=10, y=0),
            normal_side=SectionNormalSide.RIGHT,
            label_start="B",
            label_end="B",
            tail_length=2,
            text_offset=1,
            layer="A-ANNO",
            text_style="Standard",
            text_height=2.5,
        )


def test_scd_execution_writes_geometry_in_one_undo_mark():
    adapter = FakeAdapter()
    result = execute_section_mark(
        SectionMarkRequest(
            document_id="doc-1",
            mode=SectionMarkMode.DOUBLE,
            cut_start=Point3D(x=0, y=0),
            cut_end=Point3D(x=10, y=0),
            normal_side=SectionNormalSide.RIGHT,
            label_start="B",
            label_end="B",
            tail_length=2,
            double_line_gap=0.5,
            text_offset=1,
            layer="A-ANNO",
            text_style="Standard",
            text_height=2.5,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert len(result.created_handles) == 6
    assert adapter.events == ["begin", ("lines", 4), ("texts", 2), "end"]


def test_tbm_creates_missing_style_and_uses_no_hidden_values():
    request = TableStyleRequest(
        document_id="doc-1",
        desired=table_spec(),
        existing_policy=ExistingStylePolicy.ERROR,
    )
    plan = plan_table_style(request, TableStyleSnapshot(exists=False))
    assert plan.action is TableStyleAction.CREATE
    assert plan.desired.style_name == "XI_TB_N"
    assert plan.dialog_required is False


def test_tbm_rejects_different_existing_style_under_error_policy():
    request = TableStyleRequest(
        document_id="doc-1",
        desired=table_spec(),
        existing_policy=ExistingStylePolicy.ERROR,
    )
    existing = TableStyleSnapshot(exists=True, spec=table_spec(data_text_height=3.0))
    with pytest.raises(ValueError, match="already exists"):
        plan_table_style(request, existing)


def test_tbm_update_executes_in_one_undo_mark():
    adapter = FakeAdapter()
    adapter.style = TableStyleSnapshot(exists=True, spec=table_spec(data_text_height=3.0))
    result = execute_table_style(
        TableStyleRequest(
            document_id="doc-1",
            desired=table_spec(),
            existing_policy=ExistingStylePolicy.UPDATE,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.changed
    assert adapter.events == ["begin", ("style-update", "XI_TB_N"), "end"]


def test_document_mismatch_rejected():
    adapter = FakeAdapter()
    adapter.document = "other"
    with pytest.raises(ValueError, match="mismatch"):
        execute_table_style(
            TableStyleRequest(
                document_id="doc-1",
                desired=table_spec(),
                existing_policy=ExistingStylePolicy.KEEP,
            ),
            adapter,
        )
