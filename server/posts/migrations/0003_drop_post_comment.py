# Generated manually — drop Post & Comment tables (data now in Cassandra)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0002_initial"),
        ("hashtags", "0002_initial"),  # PostHashtagRel references Post
    ]

    operations = [
        # Remove indexes first
        migrations.RemoveIndex(
            model_name="comment",
            name="posts_comme_post_id_ab98e8_idx",
        ),
        migrations.RemoveIndex(
            model_name="post",
            name="posts_post_search__5398d0_idx",
        ),
        # Drop models (tables)
        migrations.DeleteModel(name="Comment"),
        migrations.DeleteModel(name="Post"),
    ]
