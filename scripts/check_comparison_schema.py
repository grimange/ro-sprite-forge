"""Offline Draft 2020-12 checks for comparison, contact sheet and sequence manifest contracts."""
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'src'), str(Path(__file__).resolve().parents[1] / 'tests')]
from importlib.resources import files
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.comparison import comparison_schema, compare_frames
from ro_sprite_forge.core.contact_sheet import (
    contact_sheet_schema,
    sequence_manifest_schema,
    generate_contact_sheet,
    export_frame_sequence,
)
from test_animation import inspector


def main():
    comp_schema = comparison_schema()
    cs_schema = contact_sheet_schema()
    seq_schema = sequence_manifest_schema()

    for schema in (comp_schema, cs_schema, seq_schema):
        Draft202012Validator.check_schema(schema)

    v_comp = Draft202012Validator(comp_schema)
    v_cs = Draft202012Validator(cs_schema)
    v_seq = Draft202012Validator(seq_schema)

    e1 = inspector(category='monster')
    e2 = inspector(category='monster')

    walk1 = e1.timeline.select(action='Walk', frame=0)
    walk2 = e2.timeline.select(action='Walk', frame=0)
    die1 = e1.timeline.select(action='Die', frame=0)

    # Positive comparison cases
    valid_comparisons = [
        compare_frames(e1, e2, walk1, walk2, mode='SIDE_BY_SIDE')['report'],
        compare_frames(e1, e2, walk1, walk2, mode='DIFFERENCE')['report'],
        compare_frames(e1, e2, walk1, walk2, mode='ONION_SKIN')['report'],
        compare_frames(e1, e2, walk1, die1, mode='SIDE_BY_SIDE')['report'],
        compare_frames(e1, None, walk1, None, mode='SIDE_BY_SIDE')['report'],
        compare_frames(e1, e2, walk1, walk2, alignment='ORIGIN', overlays=['origin', 'bounds'])['report'],
        compare_frames(e1, e2, walk1, walk2, alignment='BOUNDS_CENTER', overlays=['anchors', 'layers'])['report'],
    ]

    for comp in valid_comparisons:
        v_comp.validate(comp)

    # Positive contact sheet cases
    valid_sheets = [
        generate_contact_sheet(e1, walk1, columns=4, scale=1, labels=True)['report'],
        generate_contact_sheet(e1, die1, columns=8, scale=2, labels=False, overlays=['origin', 'bounds'])['report'],
    ]
    for cs in valid_sheets:
        v_cs.validate(cs)

    # Positive sequence manifest cases
    valid_sequences = []
    with tempfile.TemporaryDirectory(prefix='rsf-seq-check-') as tmpdir:
        seq_dir1 = Path(tmpdir) / 'seq1'
        man1 = export_frame_sequence(e1, walk1, seq_dir1, overlays=['origin'])
        valid_sequences.append(man1)

        seq_dir2 = Path(tmpdir) / 'seq2'
        man2 = export_frame_sequence(e1, die1, seq_dir2)
        valid_sequences.append(man2)

    for seq in valid_sequences:
        v_seq.validate(seq)

    # Negative comparison tests
    orig_comp = valid_comparisons[0]
    negative_comp = []
    for key, value in [('schema', 'rsf.preview-comparison/v99'), ('artistic_approval', 'APPROVED'), ('technical_difference_only', False)]:
        bad = copy.deepcopy(orig_comp); bad[key] = value; negative_comp.append(bad)
    bad = copy.deepcopy(orig_comp); del bad['reference']['sources']['body_act']; negative_comp.append(bad)
    bad = copy.deepcopy(orig_comp); bad['metrics']['max_channel_difference'] = 300; negative_comp.append(bad)
    bad = copy.deepcopy(orig_comp); bad['alignment']['policy'] = 'MAGIC_ALIGN'; negative_comp.append(bad)
    for bad in negative_comp:
        assert list(v_comp.iter_errors(bad)), f'Malformed comparison accepted: {bad}'

    # Negative contact sheet tests
    orig_cs = valid_sheets[0]
    negative_cs = []
    for key, value in [('schema', 'rsf.contact-sheet/v99'), ('grid', {'columns': 0})]:
        bad = copy.deepcopy(orig_cs); bad[key] = value; negative_cs.append(bad)
    bad = copy.deepcopy(orig_cs); del bad['grid']['columns']; negative_cs.append(bad)
    bad = copy.deepcopy(orig_cs); bad['tiles'][0]['tile_index'] = -1; negative_cs.append(bad)
    for bad in negative_cs:
        assert list(v_cs.iter_errors(bad)), f'Malformed contact sheet accepted: {bad}'

    # Negative sequence manifest tests
    orig_seq = valid_sequences[0]
    negative_seq = []
    for key, value in [('schema', 'rsf.sequence-manifest/v99'), ('frame_count', 0)]:
        bad = copy.deepcopy(orig_seq); bad[key] = value; negative_seq.append(bad)
    bad = copy.deepcopy(orig_seq); bad['frames'][0]['filename'] = '../outside.png'; negative_seq.append(bad)
    for bad in negative_seq:
        assert list(v_seq.iter_errors(bad)), f'Malformed sequence manifest accepted: {bad}'

    total_valid = len(valid_comparisons) + len(valid_sheets) + len(valid_sequences)
    total_invalid = len(negative_comp) + len(negative_cs) + len(negative_seq)
    print(f'COMPARISON_SCHEMA_PASS schemas=3 valid={total_valid} invalid={total_invalid}')


if __name__ == '__main__':
    main()
