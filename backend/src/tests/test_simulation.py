import pytest


from src.server.simulation.simulation import Simulation
from src.server.models.dataenums import ActionType, Actor, DotState
from src.server.models.request import Action



class TestSimulation():


    @pytest.mark.parametrize(
        "resolve_fixture, distance, output",
        [
            ("e_damage_aa", 0, 0),  # general
            ("e_damage_e", 0, 6),  # delay
            ("e_damage_r", 500, 8)  # travel time
        ],
    indirect=["resolve_fixture"])
    def test_calculate_delay(self, sim: Simulation, resolve_fixture, distance, output):
        sim.distance = distance
        sim.tick = 30
        result = sim._calculate_delay(resolve_fixture)
        assert result == output



    @pytest.mark.parametrize(
        "initial_queue, expected_queue",
        [
            ({}, {}),
            ({5: ["q_damage_w"]}, {5: ["q_damage_w"]}),
            ({10: ["q_damage_w"]}, {}),
            ({5: ["q_damage_w"], 10: ["q_damage_w"]}, {5: ["q_damage_w"]}),
            ({5: ["q_damage_w"], 10: ["q_damage_w", "q_damage_aa"]}, {5: ["q_damage_w"], 10: ["q_damage_aa"]})
        ]
    )
    def test_remove_dot_end(self, sim: Simulation, q_damage_w, q_damage_aa, initial_queue, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_aa": q_damage_aa
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        sim._remove_dot_end(q_damage_w.source, Actor.RED, 10)

        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped



    def test_find_existing_dot_empty(self, sim: Simulation, e_damage_w):
        sim.tick = 10
        dot_state = DotState(
            start=10,
            last_regular=10,
            end=70
        )
        result = sim._find_existing_dot(e_damage_w)
        assert result == dot_state
        assert sim.dots[(e_damage_w.source, e_damage_w.target)] == dot_state
    
    
    
    def test_find_existing_dot_expired(self, sim: Simulation, e_damage_w):
        sim.tick = 50
        sim.dots[(e_damage_w.source, e_damage_w.target)] = DotState(
            start=0,
            last_regular=30,
            end=30
        )
        result = sim._find_existing_dot(e_damage_w)

        dot_state = DotState(
            start=50,
            last_regular=50,
            end=110
        )
        assert result == dot_state
        assert sim.dots[(e_damage_w.source, e_damage_w.target)] == dot_state



    @pytest.mark.parametrize(
        "initial_queue, dot_state, expected_queue",
        [
            ({15: ["q_damage_w"]}, DotState(start=0, last_regular=15, end=15) , {15: ["q_damage_w"]}),
            ({15: ["q_damage_w"], 20: ["q_damage_w"]}, DotState(start=0, last_regular=15, end=20), {15: ["q_damage_w"]}),
        ]
    )
    def test_find_existing_dot(self, sim: Simulation, q_damage_w, e_damage_w, initial_queue, dot_state, expected_queue):
        sim.tick = 10
        sim.queue = {k: [q_damage_w for v in values] for k, values in initial_queue.items()}
        sim.dots[(e_damage_w.source, e_damage_w.target)] = dot_state
        dot_state = DotState(
            start=0,
            last_regular=15,
            end=70
        )
        result = sim._find_existing_dot(e_damage_w)

        expected_queue_mapped = {k: [q_damage_w for v in values] for k, values in expected_queue.items()}
        assert result == dot_state
        assert sim.dots[(e_damage_w.source, e_damage_w.target)] == dot_state
        assert sim.queue == expected_queue_mapped



    
    @pytest.mark.parametrize(
        "initial_queue, initial_dot_state, expected_queue, expected_dot_state",
        [
            # empty damge_queue
            ({},  # Initial state
             None,
             {15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60: ["q_damage_w"]},
             DotState(start=0, last_regular=60, end=60)),

            # Only the last dot remaining
            ({15: ["q_damage_w"]},
             DotState(start=0, last_regular=15, end=15),
             {15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60: ["q_damage_w"]},
             DotState(start=0, last_regular=60, end=60)),

            # irregular last dot
            ({15: ["q_damage_w"], 20: ["q_damage_w"]},
             DotState(start=0, last_regular=15, end=20),
             {15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60: ["q_damage_w"]},
             DotState(start=0, last_regular=60, end=60)),

            # shadow dot is in irregular distance to the last dot
            ({10: ["q_damage_w"], 15: ["q_damage_w"]},
             DotState(start=-20, last_regular=10, end=15),
             {10: ["q_damage_w"], 25: ["q_damage_w"], 40: ["q_damage_w"], 55: ["q_damage_w"], 60: ["q_damage_w"]},
             DotState(start=-20, last_regular=55, end=60)),
        ]
    )
    def test_apply_dot(self, sim: Simulation, e_damage_w, q_damage_w, initial_queue, initial_dot_state, expected_queue, expected_dot_state):
        sim.queue = {k: [q_damage_w for v in values] for k, values in initial_queue.items()}
        sim.dots[(e_damage_w.source, e_damage_w.target)] = initial_dot_state
        sim._apply_dot(e_damage_w, Actor.BLUE)
        expected_queue_mapped = {k: [q_damage_w for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped
        assert sim.dots[(e_damage_w.source, e_damage_w.target)] == expected_dot_state


    @pytest.mark.parametrize(
        "initial_queue, initial_dot_state, queue_args, expected_queue",
        [
            # empty damge_queue > W
            ({},  # Initial state
             None,
             ["e_damage_w"],  # Input
             {15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60:["q_damage_w"]}),  # Expected state

            # empty damge_queue > AA
            ({},
             None,
             ["e_damage_aa"],
             {0: ["q_damage_aa"]}),

            # empty damge_queue > AA + W
            ({},
             None,
             ["e_damage_w", "e_damage_aa"],
             {0: ["q_damage_aa"], 15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60:["q_damage_w"]}),
            
            # W > AA
            ({0: ["q_damage_w"], 15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"]},
             DotState(start=-15, last_regular=45, end=45),
             ["e_damage_aa"],
             {0: ["q_damage_w", "q_damage_aa"], 15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"]}),

            # W > W
            ({0: ["q_damage_w"], 15: ["q_damage_w"]},
             DotState(start=-45, last_regular=15, end=15),
             ["e_damage_w"],
             {0: ["q_damage_w"], 15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60:["q_damage_w"]}),

            # W > W + shadow
            ({12: ["q_damage_w"]},
             DotState(start=-48, last_regular=12, end=12),
             ["e_damage_w"],
             {12: ["q_damage_w"], 27: ["q_damage_w"], 42: ["q_damage_w"], 57: ["q_damage_w"], 60: ["q_damage_w"]}),

            # W + shadow > W + shadow
            ({6: ["q_damage_w"]},
             DotState(start=-48, last_regular=-3, end=6),
             ["e_damage_w"],
             {12: ["q_damage_w"], 27: ["q_damage_w"], 42: ["q_damage_w"], 57: ["q_damage_w"], 60: ["q_damage_w"]}),

            # shadow > W
            ({},
             DotState(start=-66, last_regular=-6, end=-6),
             ["e_damage_w"],
             {15: ["q_damage_w"], 30: ["q_damage_w"], 45: ["q_damage_w"], 60:["q_damage_w"]}),
        ]
    )
    def test_queue_status(self, sim: Simulation, e_damage_aa, e_damage_w, q_damage_w, q_damage_aa,
                          initial_queue, initial_dot_state, queue_args, expected_queue):
        sim.dots[(e_damage_w.source, e_damage_w.target)] = initial_dot_state
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_aa": q_damage_aa,
            "e_damage_aa": e_damage_aa,
            "e_damage_w": e_damage_w
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        args_mapped = [mapping[value] for value in queue_args]
        sim._queue_status(args_mapped, Actor.BLUE)
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_queue, tick, expected_queue",
        [
            # Timer before first queued damge
            ({6: ["q_damage_aa"]},  # initial state
             0,  # timer
             {6: ["q_damage_aa"]}),  # expected state

            # Timer on first queued damage
            ({6: ["q_damage_aa"]},
             6,
             {}),

            # Timer between queued damages
            ({6: ["q_damage_aa"], 15: ["q_damage_w"]},
             6,
             {15: ["q_damage_w"]}),

            # 2 damages at the same time
            ({6: ["q_damage_aa", "q_damage_w"], 21: ["q_damage_w"]},
             24,
             {})
        ]
    )
    def test_process_queue(self, sim: Simulation, q_damage_aa, q_damage_w,
                                  initial_queue, tick, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_aa": q_damage_aa,
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        sim.tick = tick
        sim._process_queue()
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped


    def test_process_queue_heal(self, sim: Simulation, q_vamp_aa):
        sim.queue = {15: [q_vamp_aa]}
        sim.tick = 30
        sim.actors[Actor.BLUE].hp = 900
        sim._process_queue()
        assert round(sim.actors[Actor.RED].hp, 3) == 1210.446
        assert round(sim.actors[Actor.BLUE].hp, 3) == 918.363


    def test_do_action(self, sim: Simulation, q_damage_aa):
        sim._do_action(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA))
        assert sim.tick == 7
        assert list(sim.queue.keys())[0] == 7
        assert list(sim.queue.values())[0][0] == q_damage_aa


    @pytest.mark.parametrize("input, output", [
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (55, 7, 1246.965)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (111, 40, 1191.67)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q)], (115, 25, 1187.131)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (115, 25, 1187.131)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (170, 40, 1131.836)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (170, 58, 1131.836)),
    ])
    def test_do_combo(self, sim: Simulation, input, output):
        result = sim.do_combo(input)
        assert result.damage == output[0]
        assert result.ticks == output[1]
        assert round(sim.actors[Actor.RED].hp, 3) == output[2]