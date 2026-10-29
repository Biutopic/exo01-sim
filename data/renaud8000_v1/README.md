# Renaud 8000 - reference reconstruction / revision 1

This editable 3D model reconstructs the Renaud 8000 from the user's archived boat photographs and specification sheet, a supplied interior plan, restored-interior photographs, and published photographs of the same model. It is a reference reconstruction, not recovered original CAD or a surveyed hull.

## Files

| File | Purpose |
|---|---|
| `Renaud8000_3D_viewer.html` | Standalone offline WebGL viewer. Orbit, top/side/bow views, removable roof, interior cutaway and component metadata. |
| `Renaud8000_reference.step` | Named, coloured CAD assembly in millimetres. |
| `Renaud8000_reference.glb` | Portable assembly in metres with embedded mass provenance and uncertainty metadata. |
| `Renaud8000_mass_metadata.json` | Authoritative mass references, missing inputs, dimensions, source register and EXO integration notes. |
| `Renaud8000_hull_envelope_PROXY.step` | Separate closed exterior envelope for future replacement/calibration. UNMEASURED and not validated as displacement geometry. Excludes keel appendix and above-deck sealed volume. It is not an extra assembly component. |
| `Renaud8000_preview.png` | Isometric rendering of the exported model. |
| `Renaud8000_reference_views.png` | Side, top, bow and cutaway reference views. |
| `parameters.json` | Editable reconstruction inputs and historical reference values. |
| `sources/` | Relevant source images recovered from the user's files, without unrelated dossier content. |

## Mass accounting

The archived specification sheet visible in `sources/archived_plans_and_boat.png` labels **light weight: 2.1 T**, transcribed as **2,100 kg**. This is a historical model reference, **not a measured weight of the user's restored boat**. The original boat photograph and the archive caption appear on page 7 of the user's municipal proposal v19.

The published [Fluvial Renaud 8000 sheet](https://www.fluvialnet.com/fiches-bateaux/renaud-8000/163) separately gives **3,000 kg**, without resolving its loading basis against the archived light weight. The two values are retained as alternative references. They are neither added nor averaged, and they are not a validated uncertainty interval.

The GLB contains one numeric mass assignment, `mass_kg: 2100`, on `RENAUD8000_BOAT_REFERENCE`. Its status explicitly identifies an unverified historical light-weight reference. `current_measured_mass_kg`, actual centre of mass and actual inertia remain **null**. The root metadata also records the alternative references; those are not additional component masses.

Hull, cabin, roof, glazing, furniture, engine, tanks and existing electrics have no measured mass breakdown. Subsystem entries retain **null**, not fabricated numbers or zero. Do not add a guessed engine or furniture mass to 2,100 kg without resolving what that historical light weight already includes. Restore/refit changes are also unknown.

Water capacity is transcribed as **350 litres**, fuel capacity as **64 litres** from the archival sheet. Installed capacities and current fill levels remain unknown. Model references vary: Fluvial gives 575/150 litres, while the separate Anjouan boat listing gives 500/140 litres. These figures do not describe measured current tanks in the user's boat. Tank capacities are not automatically converted into current fluid loads.

The user previously reported a 20 CV engine. Power is not engine mass; the current engine identity, drive, mass and position remain unconfirmed, and no invented propulsion installation is shown.

## Geometry

- Nominal length **8.00 m**, beam **2.98 m**, archival draft **0.75 m**, archival air draft **2.30 m**. These are historical specifications, not current measurement or computed flotation.
- CAD axes are right handed: **X from stern toward bow, Y to port, Z up**. The origin is at the nominal stern plane and centreline, with Z=0 at an illustrative catalogue waterline reference. It is not an equilibrium waterline.
- GLB child geometry is in metres. The root applies a -90 degree rotation around X, converting `(x,y,z) CAD` to `(x,z,-y) glTF`. Do not repeat this conversion on import. Metadata positions use CAD axes.
- The cabin retains the stepped roof, two tall saloon windows on each side, lower aft-cabin windows, forward glazed door and open forward terrace seen in the reference photos. The blue hull stripe follows the archived boat appearance.
- The interior is an indicative layout, informed by the supplied plan and restored-interior photos. It is not an as-built record of the current refit.
- The gull-wing hull is an approximate editable loft. Its station coordinates, keel, end shape and underwater sections are inferred. **No measured offsets are available.** A valid closed CAD solid does not establish an accurate displacement surface.
- The visible hull is hollowed to allow the cutaway view. `Renaud8000_hull_envelope_PROXY.step` is a separate closed proxy of the exterior body, excluding the keel. It must not be added as a second body in the displayed assembly or mass accounting.
- Nominal roof dimensions and small hardware envelopes differ slightly; do not interpret a mesh bounding box as an independently measured air draft.
- STEP preserves names and colours; it does not automatically install physical masses, densities or inertia in the importing application. Read the GLB `extras` or JSON explicitly.

## Using it with EXO-01

The boat is a separate asset. The EXO revision-3 frame, its six floats, two batteries, four panels and other listed equipment are not included in this boat model. No combined operating mass is asserted. Confirm the mounting transform, connection behaviour, boat loading state and any overlapping equipment accounting before combining the assets in a simulation. A 2,100 kg or 3,000 kg model reference plus the EXO register is not automatically a complete operating displacement.

Before computing realistic hydrostatics or wave response, measure the actual underwater hull or obtain verified lines/offsets, determine the current boat mass and loading condition, locate component masses and centres of mass, and establish the inertia distribution. Those missing properties are preserved as unknown in the files.

## Rebuild

Install `requirements.txt`, then run:

```bash
python build_model.py
python render_preview.py
python validate_model.py
```

The editable source, local viewer template and parameters are included. Builds require CadQuery; the HTML viewer itself is self-contained and needs only a browser with WebGL.

Geometry is checked by STEP reimport, GLB/STEP bounds comparison, metadata consistency and one-time mass accounting. Static renders are inspected visually. Numerical naval analysis and physical validation have not been performed. Viewer script/control checks use a mocked WebGL/DOM environment; no actual browser graphics test was available.

## Reference provenance

- User file `renaud8000.png` (`libfile_a03ed803a45481918f394812eea48e6e`): supplied interior plan.
- User file `BIUTOPIC_Erdre_Proposition_municipale_v19_final.pdf` (`libfile_98cea55c8804819182ceeab4f191e835`), p.7: archived plans/specifications and pre-restoration boat photographs; restored-interior photos are also present in the dossier.
- [Les Canalous, Renaud 8000](https://www.lescanalous.com/bateau/renaud-8000/): operator photographs and generic interior/model information.
- [Fluvial, Renaud 8000](https://www.fluvialnet.com/fiches-bateaux/renaud-8000/163): alternative published weight and specifications.
- [Anjouan, Renaud 8000](https://occasions.bateau.fr/bateau/renaud-8000-anjouan/): different individual boat; dimensions and tanks retained only as alternative references.

Web sources accessed 28 October 2026. The current owner's modifications are not established by another vessel's catalogue or listing.
