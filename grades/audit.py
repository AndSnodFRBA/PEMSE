def log_grade_change(gradebook, changed_by, change_type, model_name, record_id=None,
                      field_name='', old_value='', new_value='', notes=''):
    from .models import GradeChangeLog
    GradeChangeLog.objects.create(
        gradebook=gradebook,
        changed_by=changed_by,
        change_type=change_type,
        model_name=model_name,
        record_id=record_id,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        notes=notes,
    )
