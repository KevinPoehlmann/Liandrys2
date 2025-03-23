import pytest


from src.server.models.dataenums import ActionType



class TestDummySimulation():

    @pytest.mark.parametrize(
        "initial_damage_queue, remove_args, expected_queue",
        [
            # Only the last dot remaining
            ({0.5: ["q_damage_w"]},  # Initial state
             ([(0.5, ["q_damage_w"])], "q_damage_w"),  # Arguments to function
             {}),  # Expected result

            # shadow dot is in irregular distance to the last dot
            ({0.3: ["q_damage_w"], 0.5: ["q_damage_w_shadow"]},
             ([(0.5, ["q_damage_w_shadow"]), (0.3, ["q_damage_w"])], "q_damage_w_shadow"),
             {}),

            # removed dot shares its timestamp with another damage instance
            ({0.3: ["q_damage_w", "q_damage_aa"], 0.5: ["q_damage_aa", "q_damage_w_shadow"]},
             ([(0.5, ["q_damage_aa", "q_damage_w_shadow"]), (0.3, ["q_damage_w", "q_damage_aa"])], "q_damage_w_shadow"),
             {0.3: ["q_damage_aa"], 0.5: ["q_damage_aa"]})
        ]
    )
    def test_remove_last_dots(self, dummy_sim, e_damage_w, q_damage_w, q_damage_w_shadow, q_damage_aa,
                            initial_damage_queue, remove_args, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa
        }
        dummy_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        remove_list, remove_target = remove_args
        remove_list_mapped = [(time, [mapping[item] for item in items]) for time, items in remove_list]
        dummy_sim.remove_last_dots(e_damage_w, remove_list_mapped, mapping[remove_target])
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert dummy_sim.damage_queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_damage_queue, offset",
        [
            # empty damge_queue
            ({},  # Initial state
             0.5),  # Offset

            # Only the last dot remaining
            ({0.5: ["q_damage_w"]},
             1),

            # Only the shadow dot remaining
            ({0.4: ["q_damage_w_shadow"]},
             0.5),

            # shadow dot is in irregular distance to the last dot
            ({0.3: ["q_damage_w"], 0.4: ["q_damage_w_shadow"]},
             0.4),
        ]
    )
    def test_calculate_offset(self, dummy_sim, e_damage_w, q_damage_w, q_damage_w_shadow,
                            initial_damage_queue, offset):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
        }
        dummy_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        result = dummy_sim.calculate_offset(e_damage_w)
        assert result == offset


    @pytest.mark.parametrize(
        "initial_damage_queue, expected_queue",
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
    def test_apply_dot(self, dummy_sim, e_damage_w, q_damage_w, q_damage_w_shadow,
                       initial_damage_queue, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow
        }
        dummy_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        dummy_sim.apply_dot(e_damage_w)
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert dummy_sim.damage_queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_damage_queue, queue_args, expected_queue",
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
    def test_queue_damage(self, dummy_sim, e_damage_aa, e_damage_w, q_damage_w, q_damage_w_shadow, q_damage_aa,
                          initial_damage_queue, queue_args, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa,
            "e_damage_aa": e_damage_aa,
            "e_damage_w": e_damage_w
        }
        dummy_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        args_mapped = [mapping[value] for value in queue_args]
        dummy_sim.queue_damage(args_mapped)
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert dummy_sim.damage_queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_damage_queue, timer, expected_queue",
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
    def test_process_damage_queue(self, dummy_sim, q_damage_aa, q_damage_w, q_damage_w_shadow,
                                  initial_damage_queue, timer, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa,
        }
        dummy_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        dummy_sim.timer = timer
        dummy_sim.process_damage_queue()
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert dummy_sim.damage_queue == expected_queue_mapped


    def test_do_action(self, dummy_sim):
        dummy_sim.do_action(ActionType.AA)
        assert round(dummy_sim.timer, 3) == 0.215
        assert round(dummy_sim.dummy.hp, 3) == 919.70
        assert round(dummy_sim.dummy.damage_taken, 3) == 80.30


    @pytest.mark.parametrize("input, output", [
        ([ActionType.AA], (80, 0.22, 919.70)),
        ([ActionType.AA, ActionType.AA], (161, 1.31, 839.40)),
        ([ActionType.AA, ActionType.Q], (167, 0.82, 832.808)),
        ([ActionType.Q, ActionType.AA], (167, 0.82, 832.808)),
        ([ActionType.AA, ActionType.Q, ActionType.AA], (247, 1.31, 752.508)),
        ([ActionType.Q, ActionType.AA, ActionType.AA], (247, 1.91, 752.508)),
    ])
    def test_do_combo(self, dummy_sim, input, output):
        result = dummy_sim.do_combo(input)
        assert result.damage == output[0]
        assert result.time == output[1]
        assert round(dummy_sim.dummy.hp, 3) == output[2]



class TestV1Simulator():
    

    @pytest.mark.parametrize(
        "initial_damage_queue, remove_args, expected_queue",
        [
            # Only the last dot remaining
            ({0.5: ["q_damage_w"]},  # Initial state
             ([(0.5, ["q_damage_w"])], "q_damage_w"),  # Arguments to function
             {}),  # Expected result

            # shadow dot is in irregular distance to the last dot
            ({0.3: ["q_damage_w"], 0.5: ["q_damage_w_shadow"]},
             ([(0.5, ["q_damage_w_shadow"]), (0.3, ["q_damage_w"])], "q_damage_w_shadow"),
             {}),

            # removed dot shares its timestamp with another damage instance
            ({0.3: ["q_damage_w", "q_damage_aa"], 0.5: ["q_damage_aa", "q_damage_w_shadow"]},
             ([(0.5, ["q_damage_aa", "q_damage_w_shadow"]), (0.3, ["q_damage_w", "q_damage_aa"])], "q_damage_w_shadow"),
             {0.3: ["q_damage_aa"], 0.5: ["q_damage_aa"]})
        ]
    )
    def test_remove_last_dots(self, v1_sim, e_damage_w, q_damage_w, q_damage_w_shadow, q_damage_aa,
                            initial_damage_queue, remove_args, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa
        }
        v1_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        remove_list, remove_target = remove_args
        remove_list_mapped = [(time, [mapping[item] for item in items]) for time, items in remove_list]
        v1_sim.remove_last_dots(e_damage_w, remove_list_mapped, mapping[remove_target])
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert v1_sim.damage_queue == expected_queue_mapped

    
    @pytest.mark.parametrize(
        "initial_damage_queue, offset",
        [
            # empty damge_queue
            ({},  # Initial state
             0.5),  # Offset

            # Only the last dot remaining
            ({0.5: ["q_damage_w"]},
             1),

             # Only the shadow dot remaining
            ({0.4: ["q_damage_w_shadow"]},
             0.5),

            # Rare case, where the shadow dot is in regular interval to last dot
            ({0.5: ["q_damage_w"], 1: ["q_damage_w_shadow"]}, 
             1),

            # shadow dot is in irregular distance to the last dot
            ({0.3: ["q_damage_w"], 0.5: ["q_damage_w_shadow"]},
             0.5),
        ]
    )
    def test_calculate_offset(self, v1_sim, e_damage_w, q_damage_w, q_damage_w_shadow,
                            initial_damage_queue, offset):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
        }
        v1_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        result = v1_sim.calculate_offset(e_damage_w)
        assert result == offset

    
    @pytest.mark.parametrize(
        "initial_damage_queue, expected_queue",
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
    def test_apply_dot(self, v1_sim, e_damage_w, q_damage_w, q_damage_w_shadow,
                       initial_damage_queue, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow
        }
        v1_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        v1_sim.apply_dot(e_damage_w)
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert v1_sim.damage_queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_damage_queue, queue_args, expected_queue",
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
    def test_queue_damage(self, v1_sim, e_damage_aa, e_damage_w, q_damage_w, q_damage_w_shadow, q_damage_aa,
                          initial_damage_queue, queue_args, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa,
            "e_damage_aa": e_damage_aa,
            "e_damage_w": e_damage_w
        }
        v1_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        args_mapped = [mapping[value] for value in queue_args]
        v1_sim.queue_damage(args_mapped)
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert v1_sim.damage_queue == expected_queue_mapped


    @pytest.mark.parametrize(
        "initial_damage_queue, timer, expected_queue",
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
    def test_process_damage_queue(self, v1_sim, q_damage_aa, q_damage_w, q_damage_w_shadow,
                                  initial_damage_queue, timer, expected_queue):
        mapping = {
            "q_damage_w": q_damage_w,
            "q_damage_w_shadow": q_damage_w_shadow,
            "q_damage_aa": q_damage_aa,
        }
        v1_sim.damage_queue = {k: [mapping[v] for v in values] for k, values in initial_damage_queue.items()}
        v1_sim.timer = timer
        v1_sim.process_damage_queue()
        expected_queue_mapped = {k: [mapping[v] for v in values] for k, values in expected_queue.items()}
        assert v1_sim.damage_queue == expected_queue_mapped


    def test_do_action(self, v1_sim):
        v1_sim.do_action(ActionType.AA)
        assert round(v1_sim.timer, 3) == 0.215
        assert round(v1_sim.defender.damage_taken, 3) == 55.295
        assert round(v1_sim.defender.hp, 3) == 1246.965


    @pytest.mark.parametrize("input, output", [
        ([ActionType.AA], (55, 0.22, 1246.965)),
        ([ActionType.AA, ActionType.AA], (111, 1.31, 1191.67)),
        ([ActionType.AA, ActionType.Q], (115, 0.82, 1187.131)),
        ([ActionType.Q, ActionType.AA], (115, 0.82, 1187.131)),
        ([ActionType.AA, ActionType.Q, ActionType.AA], (170, 1.31, 1131.836)),
        ([ActionType.Q, ActionType.AA, ActionType.AA], (170, 1.91, 1131.836)),
    ])
    def test_do_combo(self, v1_sim, input, output):
        result = v1_sim.do_combo(input)
        assert result.damage == output[0]
        assert result.time == output[1]
        assert round(v1_sim.defender.hp, 3) == output[2]