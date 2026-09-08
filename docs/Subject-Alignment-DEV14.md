# Selected subjects at different distances — DEV14

DEV14 addresses a near hand aligning while a farther face remains offset.
Distance itself does not require a separate mode: each target needs its own
optical display transform. The automatic matcher still cannot guarantee perfect
registration for every subject or tightly cropped face.

## Changes

- A selected patch no longer has to enclose an entire object. Interior measured
  edges are retained when a silhouette cannot be isolated.
- Selection boundaries are excluded from silhouette matching. Masks locate the
  subject; original image gradients locate its edges, avoiding mask enlargement.
- Coarse search uses a wider edge tolerance, followed by tighter refinement.
  Scale and rotation can vary around the selected target center instead of
  causing an unintended translation around the sensor center.
- **Match shared points** offers zoomed, alternating thermal/optical clicks.
  Three to eight matching, noncollinear points solve offset, uniform scale and
  rotation independently of the previous subject's distance. Badly inconsistent
  pairs are rejected. Undo corrects a click; Preview and Apply remain separate.
  The automatic-preview button retains a completed point fit rather than
  searching away from the explicit correspondences.
- Zoomed clicks map back to original sensor coordinates. Crop bounds stay fixed
  during a rectangle drag. Thermal arrays, measurement geometry, recording
  formats, optical capture resolution and power instruments are unchanged.

## Verification

93 tests passed, including a new automatic near-to-far synthetic subject test,
exact recovery from shared points at two different target transforms, rejection
of degenerate/inconsistent points, zoom coordinate mapping and Apply guards.

Six previously captured hardware pairs were rerun and their rendered crops
inspected locally: all three enclosure frames and two of three bottle frames
produced accepted improved fits; one bottle frame remained ambiguous. Inputs
were checked for unchanged numerical arrays and optical bytes.

A farther face in recorded hardware frame 8000 was tested with three nested
selection rectangles. One automatic fit was accepted; two remained ambiguous.
These results do not establish universal automatic face alignment. A native UI
test on the same recorded pair used three shared facial features and produced
a displayed RMS residual of 1.87 thermal pixels. The resulting enlarged preview
was visually inspected. That residual measures agreement with the operator's
clicks, not independent accuracy across the whole face.

The final DEV14 native app reconnected to the TC001 Max at full 256×192 thermal
and 1024×768 optical resolution, approximately 25 fps. On fresh frozen frame 212,
a selected farther face returned an automatic outline fit: dx −18.8125,
dy −9.4057, scale 1.30537, angle −2.1°. Its enlarged preview was inspected at the
nose, forehead and face boundary, then applied and confirmed in the saved workspace.
The runtime error log was empty. This is a successful live case, not a claim that
the remaining ambiguous recorded selections now pass.

All camera pictures and diagnostic outputs remain local under ignored runtime
directories. `runtime/face-dev14.json`, `runtime/face-dev14.png` and the
`runtime/edge-check/` artifacts contain the local regression results.

## Use and limits

Select the subject, Preview auto-alignment and inspect it. If it remains offset,
choose Match shared points, click three or more corresponding features within
that subject, Preview point fit, then Apply to live. No distance entry or manual
numerical adjustment is needed. Turn off Zoom selected target if the optical
subject lies outside its initial crop.

Registration does not change lens focus or recover missing sensor detail.
Viewpoint differences, thermal/visible feature differences, occlusions, movement
and depth variation within a face can prevent perfect pixel correspondence.
The displayed error is not calibration accuracy. Refit when the subject or its
distance changes; this is a frozen-pair fit, not continuous subject tracking.
