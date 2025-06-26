# TODO
## Major Enhancements
- For Reddit posts that link directly to a 3rd party asset (image or URL) rather than a reddit discussion, provide the link to BOTH the reddit thread AND the item.
  
  **Technical Implementation Steps:**
  1. **Analyze current Reddit data structure** to understand how URLs are currently handled
  2. **Identify link posts** using PRAW's submission properties (`is_self`, `url`, `permalink`)
  3. **Modify Reddit client** to capture both URLs for link posts
  4. **Update email templates** with conditional display logic
  5. **Test with different post types** (self posts, image posts, article links, etc.)
  6. **Update existing tests** to handle new data structure
  
  **Data Structure Enhancement:**
  - Extend Reddit item data to include:
    - `external_url`: The original 3rd party link
    - `reddit_url`: The Reddit discussion thread URL
    - `post_type`: Indicator of whether it's a link post or self post
  
  **Edge Cases to Consider:**
  - Reddit-hosted images/videos (v.redd.it, i.redd.it)
  - Cross-posts and shared content
  - Deleted or removed external content
  - Very long URLs in email formatting
- Add the capability to optionally filter a subreddit by a configurable minimum score threshhold.
- Add the capability to optionally filter a subreddit by lists of reddit flair to exclude

## Long term
- Find new sources that we can include alongside Reddit and Youtube