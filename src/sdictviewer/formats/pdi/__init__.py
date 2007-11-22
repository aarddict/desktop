def can_open(file_name):
    before, sep, after = file_name.rpartition(".")
    return after == 'pdi'