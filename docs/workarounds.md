# Bypassing Instagram 403 Errors in Instaloader 4.15.1

## Overview
Instagram blocks anonymous requests to `graphql/query` with `doc_id=8845758582119845`, causing `Post._obtain_metadata()` to fail with HTTP 403. This prevents comment fetching.

## Workaround 1: Authenticated Sessions
Use a logged-in session to bypass 403 errors:

```python
from instaloader import Instaloader

L = Instaloader()
L.load_session_from_file('username')  # Load cookies
```

## Workaround 2: Pre-Load Metadata
Manually inject metadata (e.g., comment count) to avoid API calls:

```python
post = Post.from_shortcode(context, shortcode)
post.inject_metadata({"edge_media_to_comment": {"count": 100}})
print(post.comments)  # Returns 100 without API call
```

## Workaround 3: Monkey-Patching (Advanced)
If you need to patch `Post._obtain_metadata` globally:

```python
from instaloader.structures import Post

original_obtain_metadata = Post._obtain_metadata

def patched_obtain_metadata(self):
    if "edge_media_to_comment" in self._node:
        return  # Skip API call if comments are pre-loaded
    try:
        original_obtain_metadata(self)
    except Exception as e:
        if hasattr(self, "_iphone_struct") and self._iphone_struct:
            self._full_metadata_dict = {"xdt_shortcode_media": self._iphone_struct}
        else:
            raise

Post._obtain_metadata = patched_obtain_metadata
```

## Workaround 4: Use iPhone Struct
If you have a logged-in session, use the iPhone struct for metadata:

```python
post = Post.from_shortcode(context, shortcode)
iphone_struct = post._iphone_struct  # Requires login
print(iphone_struct.get('comment_count', 0))
```

## Notes
- The `inject_metadata` method is the simplest workaround for most use cases.
- Authenticated sessions are required for the iPhone endpoint.
- Monkey-patching is only needed if you cannot modify the source code.
