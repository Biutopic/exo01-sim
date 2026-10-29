# EXO-01 — reference 3D assembly and mass register / revision 3

Prepared from **La Mutine, “ASSEMBLAGE HYDRONAUTE”, 28 May 2026, sheet 1/3**, and the component masses supplied on 28 October 2026. Revision 3 incorporates the user’s annotated image `source_annotation.jpeg` and subsequent clarification: the observation platform is about 50 cm below the top frame, the four panels form one row with front overhang only, and the existing float shapes are retained. This is a reconstructed reference model, not a recovery of the original CAD file.

## Open the model

| File | Purpose |
|---|---|
| `EXO01_3D_viewer.html` | Standalone interactive viewer. Open in a browser with WebGL. Rotate, change view, hide panels and select component metadata. No internet connection or installation required. |
| `EXO01_reference.step` | Editable solid assembly for a CAD application. Units: millimetres. Component names include their assigned masses. |
| `EXO01_reference.glb` | Lightweight 3D assembly. Units: metres. Full component mass properties and uncertainty notes are embedded in each component node’s `extras`. |
| `EXO01_mass_metadata.json` | Authoritative, readable mass register, coordinate conventions, assumptions and missing engineering information. |
| `EXO01_preview.png` | Isometric preview of the actual exported geometry. |
| `EXO01_reference_views.png` | Top, side and end views. |
| `parameters.json` | Editable geometry and mass inputs for regeneration. |
| `source_plan.webp` | Unmodified dimensioned source drawing supplied by the user. |
| `source_annotation.jpeg` | User correction identifying the observation area and panel alignment. |

**Use the GLB or JSON for metadata.** STEP retains solid geometry, colours and assembly names with mass labels, but it does not carry the full JSON metadata as physical material or mass properties. A CAD/game application must explicitly read `mass_kg` or the sidecar register before using these masses. No automatic density-based material assignment or rigid-body simulation is configured.

## Supplied masses

| Components | Quantity | Mass each | Subtotal |
|---|---:|---:|---:|
| Batteries | 2 | 120 kg | 240 kg |
| Solar panels | 4 | 20 kg | 80 kg |
| Electronics and miscellaneous equipment | 1 group | approximately 50 kg | 50 kg |
| Rear EXO section | 1 | 150 kg | 150 kg |
| Other EXO sections | 2 | 70 kg | 140 kg |
| Floats | 6, confirmed by user | 30 kg | 180 kg |
| **Total listed components** | **16 mass-bearing groups** | | **840 kg** |

The section weights are treated as separate from the floats and equipment. If a 150 kg or 70 kg section measurement already includes any of those items, its entry must be corrected to avoid counting them twice. All masses are user supplied; no independent weighing or tolerance is available.

The **upper observation deck surface** is represented geometrically, but its additional mass is unknown: it may already be included in the 70 kg middle-section value. This inclusion is explicitly unconfirmed in the metadata. People on the upper deck are separate loads; their mass and body centres of mass have not been assigned. The 840 kg is **not a complete vessel displacement**. The host boat, people, payload, propulsion and other unlisted equipment are not assigned invented zero masses; their values remain unknown and are outside this register.

## Geometry and coordinates

- CAD is right handed, in millimetres. X runs from the open rear deck edge toward the framed end. Y is transverse. Z points upward from the nominal deck datum. Port/starboard and bow/stern are not asserted.
- The model follows the section length chain: **2100 + 1425 + 1425 = 4950 mm**. The separate **4980 mm** dimension is recorded as a **30 mm unresolved discrepancy**. The model is not silently stretched to satisfy both.
- Frame width is **4547 mm** and frame height above the deck datum is **2700 mm**. The **2100 mm** clearance and **600 mm** ladder width are retained. The other **3200 / 3353 mm** clearances are documented but not treated as independently solved constraints.
- GLB child geometry is in metres, initially in CAD axes. The root applies a −90° rotation about X to obtain standard glTF Y-up: `(x, y, z) CAD → (x, z, −y) glTF`. Positions in JSON metadata remain in the documented CAD coordinate system, in metres.
- Overall proxy bounds can exceed the nominal frame dimensions because floats and equipment project beyond the frame.

## Assumptions to confirm

1. **Mass-to-section mapping:** the 2100 mm rear platform is assigned 150 kg; the two 1425 mm bays are assigned 70 kg each. A module’s mass includes its modelled rails, ladder/stand or bracing as a bookkeeping group, not a measured mass distribution between its members.
2. **Float geometry:** six independent floats are modelled, three per side. Diameter, end shape, lengths and locations are inferred envelopes. They are not measured displacement surfaces. The default diameter is 580 mm; this is an assumption, not a drawing dimension. Revision 3 retains the six float shapes, positions and masses unchanged from revision 2, as requested.
3. **Roof layout:** the observation walking surface is modelled at **2.200 m**, about **0.500 m below the nominal top-frame level**, following the user’s clarification. The ladder meets this level; adjacent proxy headers sit under the 24 mm deck while retaining the nominal 2.100 m underside clearance. Those header sizes are visual envelopes, not engineered sections. Four panels sit side by side across the remaining end bay, with their long dimensions along X. They have **zero side overhang**. To fit the frame width with three provisional 40 mm gaps, the preview panel envelopes are 2060 × 1106.75 mm each. These are **fitted model dimensions, not measurements of the real panels**. Only the front (+X framed end) projects beyond the frame, by a provisional 635 mm. The user’s “front” is interpreted as this existing projecting end. Exact panel dimensions, front overhang, tilt and mounting details remain unresolved; the panels are shown horizontal for now.
4. **Batteries/electronics:** orange batteries and teal electronics are illustrative boxes in provisional positions. Actual dimensions, mount locations and centres of mass have not been provided.
5. **Structure:** beam/profile and connection-plate shapes are simplified solid envelopes. Tube wall thickness, alloy, welds, fasteners and real stiffness are unknown. **Do not derive section masses or structural capacity from the proxy solid volumes.**

## What this version does and does not establish

The model provides a named 3D assembly and a non-duplicated register of the 16 masses. `mass_kg` is stored once at each component parent. The added observation-deck surface has `surface_mass_kg: null` and `mass_is_in_parent: null`, to record unresolved inclusion in the middle-section mass. Other child meshes refer to the parent and are not counted separately. `pending_loads` records the unresolved surface mass and occupant load.

The overall centre of gravity and inertia tensor are deliberately **null**, not estimated from the placeholder placements. No equilibrium waterline, stability curve, wave response or structural strength has been calculated. No configuration or load limit is approved by this reconstruction.

Before the next engineering step, obtain the actual float cross-sections/volumes, battery and equipment locations, component centres of mass or material distribution, complete host-vessel geometry/mass, and confirmation of the mass-accounting and length discrepancy. Sheets 2/3 and 3/3 or the original CAD would reduce the reconstruction uncertainty.

## Rebuild and inspect

Install the packages in `requirements.txt`, edit `parameters.json`, then run:

```bash
python build_model.py
python render_preview.py
python validate_model.py
```

`build_model.py` produces the STEP, GLB, JSON and standalone viewer. `viewer_template.html` is required beside it. `render_preview.py` makes the PNG previews from the exported tessellation using a software depth buffer; it requires `preview_mesh.json`, which the build creates. The cache need not be edited manually.

Validation checks the STEP round trip, component masses, GLB structure/units, geometry bounds and explicit unknown engineering fields. The viewer receives syntax and control-logic checks; a real browser/WebGL visual test was unavailable in the creation environment. The PNG previews were rendered and visually inspected.

## Format references

- [CadQuery assembly export](https://cadquery.readthedocs.io/en/latest/importexport.html)
- [Khronos glTF 2.0 specification: application metadata in extras](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
