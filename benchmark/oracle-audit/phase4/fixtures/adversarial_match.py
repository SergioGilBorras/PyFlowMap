"""Generic source fixture for adversarial Phase 4 match-oracle tests."""


def classify(message, enabled):
    match message:
        case {"kind": "item", "value": value} if enabled(value):
            consume(value)
        case _:
            skip()


def two_dispatches(first, second):
    match first:
        case "alpha":
            alpha_path()
        case _:
            first_fallback()

    match second:
        case "beta":
            beta_path()
        case _:
            second_fallback()


def compound_guard(message, primary, secondary):
    match message:
        case {"value": value} if primary(value) and secondary(value):
            consume(value)
        case _:
            skip()


def non_exhaustive(message):
    match message:
        case "ready":
            selected()
    after_match()


def nested_and_repeated(message, other):
    match message:
        case {"outer": inner}:
            match inner:
                case "ready":
                    ready_path()
                case _:
                    inner_fallback()
        case _:
            outer_fallback()

    for item in other:
        match item:
            case "keep":
                keep_item(item)
            case _:
                skip_item(item)
