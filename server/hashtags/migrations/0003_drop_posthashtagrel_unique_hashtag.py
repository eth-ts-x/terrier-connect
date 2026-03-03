# Generated manually — drop PostHashtagRel, add unique constraint to Hashtag

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hashtags", "0002_initial"),
        ("posts", "0003_drop_post_comment"),  # PostHashtagRel FK to Post
    ]

    operations = [
        migrations.DeleteModel(name="PostHashtagRel"),
        migrations.AlterField(
            model_name="hashtag",
            name="hashtag_text",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
