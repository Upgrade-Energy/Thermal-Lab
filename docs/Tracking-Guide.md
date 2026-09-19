# Recording the hottest and coldest points

Named trackers find the hottest or coldest **thermal pixel on every frame**. You do not need to know its position beforehand. They store both its numerical temperature and location; they are separate from the optional overview markers.

## Record a tracker

1. Connect the camera. Open the **Measure** tab.
2. Under **Track a moving extreme**, leave **Search → Whole image** to search the full thermal image.
3. Click **Track hottest**, **Track coldest**, or both. The trackers appear in **Points & regions** with a temperature and `(pixel x, pixel y)` position. Adding the same rule and region again selects the existing tracker.
4. Select a tracker and use **Selected measurement name → Rename** to give it a useful name, such as “Pack hotspot”. Its identity stays the same through renaming.
5. Click **Record session**. Click **Stop recording** when finished. Trackers use these recording controls; there is no separate tracking recorder. The recording timer shows the session duration.
6. **Show CSV** locates the automatically saved `measurements.csv`. **Recordings** opens review.

Trackers added during recording begin with the next accepted settings update. Removing one ends its history from that update onward. No values are invented for periods when it was absent. A stale/disconnected preview hides tracker values.

## Limit the search to a component

Draw a **Rectangle** or **Polygon** around the component, select that region in the measurement list, then choose **Search → Selected region** and add a tracker. Polygon tracking searches inside the polygon, not its bounding rectangle. You can click both tracking buttons in succession to add a hot and cold tracker for the same region.

The tracker follows edits to that region. It cannot be dragged to a fixed location. Removing a region also removes its dependent trackers; **Clear all points** removes fixed points and trackers while retaining the regions.

Regions are fixed in thermal image coordinates unless you edit them. A tracker follows the current extreme within its search region, not a recognized physical object. Equal temperatures choose the first pixel in row-major sensor order. Both tracker histories are retained even when all temperatures are equal.

## Review and export

- In **Layout → Recorded**, playback and scrubbing restore each tracker at its saved position. Selecting its measurement row selects its temperature history. Click the graph to seek to a time.
- **Export → Export history CSV** includes the temperature and coordinates for each sample. **Save PNG / Export MP4** with temperature labels includes named trackers at their per-frame positions.
- For an older recording without trackers, choose **Layout → Analysis**, then add hot/cold trackers. These rules are applied to every original numerical frame. Draw a region in Analysis first if you want to limit that search. Edits autosave to a separate analysis file; the recording is unchanged.
- **Show hot / cold markers** controls the optional overview overlay. Named measurement trackers remain visible and recorded independently of that checkbox.

## Coordinate and quality details

CSV `pixel_x` and `pixel_y` are zero-based column and row in the original 256 × 192 thermal sensor image. `x` and `y` are normalized pixel-center coordinates. Display rotation, optical alignment, opacity and palette do not change these coordinates or temperatures. `tracking` is `hottest` or `coldest`; `region_id` identifies a selected search region (blank for the whole image).

Tracking uses the original numerical temperatures with no smoothing, averaging, resizing or rounding before storage. The displayed label is rounded for readability; the CSV and archive retain full precision. Existing temperature accuracy qualifications still apply.

For Power Lab, save the updated layout in Thermal Lab, then re-import that layout into Power Lab for the linked camera. Sessions use those definitions through the Thermal Lab service. Saved camera archives retain these trackers and can be opened in standalone Thermal Lab review. The tracker feature does not command power instruments.
