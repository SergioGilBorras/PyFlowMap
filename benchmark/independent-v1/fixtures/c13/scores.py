def normalize(score):
    return max(0, score)

def build_index(records, minimum):
    students = [name for name, score in records if score >= minimum]
    ranking = {name: normalize(score) for name, score in records if name in students}
    pending = (normalize(score) for name, score in records if name not in ranking)
    return ranking, pending
