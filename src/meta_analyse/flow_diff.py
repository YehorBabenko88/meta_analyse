"""Compare immutable flow rows; positions are snapshot positions, not Qt rows."""
def changed_rows(previous, current):
    rebuild = tuple(row.symbol for row in previous) != tuple(row.symbol for row in current)
    if rebuild:
        return tuple(range(len(current))), True
    return tuple(i for i, row in enumerate(current) if row != previous[i]), False
