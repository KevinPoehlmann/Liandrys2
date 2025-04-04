import pytest


from src.server.models.dataenums import Action, ActionType, Actor



class TestSimulation():


    @pytest.mark.parametrize(
        "resolve_fixture, distance, output",
        [
            ("e_damage_aa", 0, 1),  # general
            ("e_damage_e", 0, 1.2),  # delay
            ("e_damage_r", 500, 1.25)  # travel time
        ],
    indirect=["resolve_fixture"])
    def test_calculate_delay(self, sim,
                                    resolve_fixture, distance, output):
        sim.distance = distance
        sim.timer = 1
        result = sim._calculate_delay(resolve_fixture)
        assert result == output
    

    @pytest.mark.parametrize(
        "initial_queue, remove_args, expected_queue",
        [
            # Only the last dot remaining
            ({1.5: ["q_damage_w"]},  # Initial state
             ([(1.5, ["q_damage_w"])], "q_damage_w"),  # Arguments to function
             {}),  # Expected result

            # shadow dot is in irregular distance to the last dot
            ({1.3: ["q_damage_w"], 1.5: ["q_damage_w_shadow"]},
             ([(1.5, ["q_damage_w_shadow"]), (1.3, ["q_damage_w"])], "q_damage_w_shadow"),
             {}),

            # removed dot shares its timestamp with another damage instance
            ({1.3: ["q_damage_w", "q_damage_aa"], 1.5: ["q_damage_aa", "q_damage_w_shadow"]},
             ([(1.5, ["q_damage_aa", "q_damage_w_shadow"]), (1.3, ["q_damage_w", "q_damage_aa"])], "q_damage_w_shadow"),
             {1.3: ["q_damage_aa"], 1.5: ["q_damage_aa"]})
        ]
    )
    def test_remove_last_dots(self, sim, e_damage_w, q_damage_w, q_damage_w_shadow, q_damage_aa,
                            initial_queue, remove_args, expected_queue):
        sim.timer = 1
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        remove_list, remove_target = remove_args
        remove_list_mapped = [(time, [mapping[item] for item in items]) for time, items in remove_list]
        sim._remove_last_dots(e_damage_w, remove_list_mapped, mapping[remove_target])
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped

    
    @pytest.mark.parametrize(
        "initial_queue, offset",
        [
            # empty damge_queue
            ({},  # Initial state
             1.5),  # Offset

            # Only the last dot remaining
            ({1.5: ["q_damage_w"]},
             2),

             # Only the shadow dot remaining
            ({1.4: ["q_damage_w_shadow"]},
             1.5),

            # shadow dot is in irregular distance to the last dot
            ({1.3: ["q_damage_w"], 1.5: ["q_damage_w_shadow"]},
             1.5),
        ]
    )
    def test_calculate_offset(self, sim, e_damage_w, q_damage_w, q_damage_w_shadow,
                            initial_queue, offset):
        sim.timer = 1
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        result = sim._calculate_offset(e_damage_w, Actor.BLUE)
        assert result == offset

    
    @pytest.mark.parametrize(
        "initial_queue, expected_queue",
        [
            # empty damge_queue
            ({},  # Initial state
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]}),  # Offset

            # Only the last dot remaining
            ({0.5: ["q_damage_w"]},
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]}),

            # Rare case, where the shadow dot is in regular interval to last dot
            ({0.5: ["q_damage_w"], 1: ["q_damage_w_shadow"]}, 
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]}),

            # shadow dot is in irregular distance to the last dot
            ({0.3: ["q_damage_w"], 0.5: ["q_damage_w_shadow"]},
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]}),

            # shadow dot is in irregular distance to the last dot
            ({0.2: ["q_damage_w"], 0.4: ["q_damage_w_shadow"]},
             {0.4: ["q_damage_w"], 0.9: ["q_damage_w"], 1.4: ["q_damage_w"], 1.9: ["q_damage_w"], 2.4: ["q_damage_w_shadow"]}),

            # shadow dot is the last one remaining
            ({0.4: ["q_damage_w_shadow"]},
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]}),
        ]
    )
    def test_apply_dot(self, sim, e_damage_w, q_damage_w, q_damage_w_shadow,
                       initial_queue, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        sim._apply_dot(e_damage_w, Actor.BLUE)
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_queue, queue_args, expected_queue",
        [
            # empty damge_queue > W
            ({},  # Initial state
             ["e_damage_w"],  # Input
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"], 2:["q_damage_w"]}),  # Expected state

            # empty damge_queue > AA
            ({},
             ["e_damage_aa"],
             {0: ["q_damage_aa"]}),

            # empty damge_queue > AA + W
            ({},
             ["e_damage_w", "e_damage_aa"],
             {0: ["q_damage_aa"], 0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"], 2:["q_damage_w"]}),
            
            # W > AA
            ({0: ["q_damage_w"], 0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]},
             ["e_damage_aa"],
             {0: ["q_damage_w", "q_damage_aa"], 0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"]}),

            # W > W
            ({0: ["q_damage_w"], 0.5: ["q_damage_w"]},
             ["e_damage_w"],
             {0: ["q_damage_w"], 0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"], 2:["q_damage_w"]}),

            # W > W + shadow
            ({0.4: ["q_damage_w"]},
             ["e_damage_w"],
             {0.4: ["q_damage_w"], 0.9: ["q_damage_w"], 1.4: ["q_damage_w"], 1.9: ["q_damage_w"], 2.0: ["q_damage_w"], 2.4: ["q_damage_w_shadow"]}),

            # W + shadow > W + shadow
            ({0.2: ["q_damage_w"], 0.4: ["q_damage_w_shadow"]},
             ["e_damage_w"],
             {0.4: ["q_damage_w"], 0.9: ["q_damage_w"], 1.4: ["q_damage_w"], 1.9: ["q_damage_w"], 2.0: ["q_damage_w"], 2.4: ["q_damage_w_shadow"]}),

            # shadow > W
            ({0.3: ["q_damage_w_shadow"]},
             ["e_damage_w"],
             {0.5: ["q_damage_w"], 1: ["q_damage_w"], 1.5: ["q_damage_w"], 2:["q_damage_w"]}),
        ]
    )
    def test_queue_status(self, sim, e_damage_aa, e_damage_w, q_damage_w, q_damage_w_shadow, q_damage_aa,
                          initial_queue, queue_args, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
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
        "initial_queue, timer, expected_queue",
        [
            # Timer before first queued damge
            ({0.2: ["q_damage_aa"]},  # initial state
             0,  # timer
             {0.2: ["q_damage_aa"]}),  # expected state

            # Timer on first queued damage
            ({0.2: ["q_damage_aa"]},
             0.2,
             {}),

            # Timer between queued damages
            ({0.2: ["q_damage_aa"], 0.5: ["q_damage_w"]},
             0.2,
             {0.5: ["q_damage_w"]}),

            # 2 damages at the same time
            ({0.2: ["q_damage_aa", "q_damage_w"], 0.7: ["q_damage_w"]},
             0.8,
             {})
        ]
    )
    def test_process_queue(self, sim, q_damage_aa, q_damage_w, q_damage_w_shadow,
                                  initial_queue, timer, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa,
        }
        sim.queue = {k: [mapping[v] for v in values] for k, values in initial_queue.items()}
        sim.timer = timer
        sim._process_queue()
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert sim.queue == expected_queue_mapped


    def test_process_queue_heal(self, sim, q_vamp_aa):
        sim.queue = {0.5: [q_vamp_aa]}
        sim.timer = 1
        sim.actors[Actor.BLUE].hp = 900
        sim._process_queue()
        assert round(sim.actors[Actor.RED].hp, 3) == 1210.446
        assert round(sim.actors[Actor.BLUE].hp, 3) == 918.363


    def test_do_action(self, sim, q_damage_aa):
        sim._do_action(Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA))
        assert round(sim.timer, 3) == 0.215
        assert round(list(sim.queue.keys())[0], 3) == 0.215
        assert list(sim.queue.values())[0][0] == q_damage_aa


    @pytest.mark.parametrize("input, output", [
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (55, 0.22, 1246.965)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (111, 1.31, 1191.67)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q)], (115, 0.82, 1187.131)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (115, 0.82, 1187.131)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (170, 1.31, 1131.836)),
        ([Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.Q), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA), Action(actor=Actor.BLUE, target=Actor.RED, action_type=ActionType.AA)], (170, 1.91, 1131.836)),
    ])
    def test_do_combo(self, sim, input, output):
        result = sim.do_combo(input)
        assert result.damage == output[0]
        assert result.time == output[1]
        assert round(sim.actors[Actor.RED].hp, 3) == output[2]