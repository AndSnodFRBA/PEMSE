"""Who can be targeted by a What's New note in this training portal."""

AUDIENCES = [
    ("all", "Everyone"),
    ("staff", "Office staff and admins"),
    ("instructors", "Instructors"),
    ("students", "Students"),
]


def is_staff_user(user):
    return bool(getattr(user, "is_office_staff", False) or user.is_staff or user.is_superuser)


def user_audiences(user):
    keys = {"all"}
    if is_staff_user(user):
        keys.add("staff")
    elif getattr(user, "is_instructor", False):
        keys.add("instructors")
    else:
        keys.add("students")
    return keys
