from src.ai.command_parser import parse_command

def test_move_layer_command():
    cmd = parse_command({'command':'move_layer','params':{'layer':'A-WALL','dx':100,'dy':0,'dz':0}})
    assert cmd.command == 'move_layer'
    assert cmd.params.layer == 'A-WALL'
