from tortoise import fields
from tortoise.models import Model


class Session(Model):

    id = fields.UUIDField(pk=True)
    title = fields.CharField(max_length=255, default="Untitled session")

    status = fields.CharField(max_length=50, default="idle")

    pending_code = fields.TextField(null=True)
    pending_plan = fields.TextField(null=True)

    current_stl_path = fields.CharField(max_length=512, null=True)
    current_png_path = fields.CharField(max_length=512, null=True)

    iteration = fields.IntField(default=0)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    messages: fields.ReverseRelation["Message"]
    cad_models: fields.ReverseRelation["CADModel"]
    jobs: fields.ReverseRelation["CADJob"]

    class Meta:
        table = "sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session({self.id}, {self.title}, {self.status})"


class Message(Model):

    id = fields.IntField(pk=True)

    session = fields.ForeignKeyField(
        "models.Session",
        related_name="messages",
        on_delete=fields.CASCADE,
    )

    role = fields.CharField(max_length=50)
    content = fields.TextField()

    code = fields.TextField(null=True)
    plan = fields.TextField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"Message({self.role}, {self.content[:50]})"


class CADModel(Model):

    id = fields.IntField(pk=True)

    session = fields.ForeignKeyField(
        "models.Session",
        related_name="cad_models",
        on_delete=fields.CASCADE,
    )

    stl_path = fields.CharField(max_length=512)
    png_path = fields.CharField(max_length=512, null=True)

    iteration = fields.IntField(default=1)

    approved = fields.BooleanField(default=False)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "cad_models"
        ordering = ["-created_at"]


class CADJob(Model):
    id = fields.UUIDField(pk=True)
 
    session = fields.ForeignKeyField(
        "models.Session",
        related_name="jobs",
        on_delete=fields.CASCADE,
    )
 
    status = fields.CharField(max_length=50, default="pending")
 
    code = fields.TextField()
 
    stdout = fields.TextField(null=True)
    stderr = fields.TextField(null=True)
    duration_ms = fields.IntField(null=True)
 
    iteration = fields.IntField(default=1)
 
    stl_path = fields.CharField(max_length=512, null=True)
    png_path = fields.CharField(max_length=512, null=True)
 
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "cad_jobs"
        ordering = ["-created_at"]


    def __str__(self):
        session_id = getattr(self, "session_id", None)
        return f"CADJob(session={session_id}, iteration={self.iteration})"
