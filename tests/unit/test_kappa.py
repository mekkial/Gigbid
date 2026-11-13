from evals.runners.judge_calibration import cohen_kappa, quad_kappa


def test_kappa_perfect_chance_and_known_value():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert abs(cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-9                   # agreement equals chance
    # textbook example: 20 pos/ 5 / 10 / 15 table -> kappa 0.4
    a = [1] * 25 + [0] * 25; b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
    assert abs(cohen_kappa(a, b) - 0.4) < 1e-9


def test_weighted_kappa_penalises_far_disagreement_more():
    near = quad_kappa([1, 2, 3, 4, 5], [2, 3, 4, 5, 5]); far = quad_kappa([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
    assert near >= 0.8 > 0 > far
