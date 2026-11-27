# Forms for records

This reference covers the file side of boards on which users create, edit and
delete records (master data, settings, assets): how the shape of
board-assets.md maps onto the navigation patterns of board-navigation.md, the
delete form in YAML, uploading files with a form, and photos taken with a form. The rules themselves (the
lists, the "New" form, the edit and delete forms and where they go) are in
board-assets.md: read it first. It assumes the board's anatomy and the literal
prefixes (`$str:`, `$num:`, `$bool:`) from board-template.md, "Anatomy" and
"Literal values".

## Boards that manage assets

Boards on which users inspect, create, change and delete assets get one
familiar shape, described in [board-assets.md](board-assets.md). In terms of
the navigation patterns of [board-navigation.md](board-navigation.md), it has
the asset types as the main menu (pattern 1), each type's data-driven widget-sidenav
with absolute item routes (pattern 2) and a "New" floating action button on
top, the detail page with the edit form and delete (pattern 6), tab pages for
further aspects (pattern 4), sub-assets one level down (pattern 3), an explicit
back button where an asset's pages leave the list out, and the tiling of an
asset's tab page. The validator follows an empty widget-navbutton route one
level up, as the widget does.

## Records that users create, edit and delete

Records that users create, edit and delete (master data, settings): a
data-driven widget-sidenav lists the records (board-navigation.md, pattern 2
or 3) and opens one
page per record (`/settings/machines/*`). A "New" form
(`formButton: $bool:true`) sits as a floating action button on top of that
sidenav, and the list page itself shows an overview of all records, such as a
table. Editing and deleting take two widget-forms, an edit form and a
separate delete form (from widget-form 2.0 on, a form has no delete button of
its own), offered as icons in the overview table that open them as dialogs,
on the record's page, or both. [board-assets.md](board-assets.md), sections
3 to 7, has the rules: both forms and both ways to offer them with their
tiles, where a form button goes, the delete flag, and binding every list to
the table itself.

The delete form on the record's page:

```yaml
- layout_id: delete-machine
  package_name: widget-form
  version: 2.0.1                       # 2.0.0 or later
  chartconfig:
      title: $str:Delete this machine?
      formButton: $bool:true
      formButtonStyle:                  # a red "Delete" button, not a round one
          fab: $bool:false
          label: $str:Delete
          iconName: $str:delete
          bgColor: $str:#dc2626         # the preset's alarm red (office here)
      accentColor: $str:#dc2626         # the dialog's Delete button
      buttonLabels:
          submitLabel: $str:Delete
          cancelLabel: $str:Keep
      submitNavigationRoute: $str:/settings/machines
      formFields:                       # what follows, and the two hidden fields
          - type: $str:section
            description: $str:It leaves every list. Its recorded data is kept.
          - label: $str:Machine
            type: $str:textfield
            hiddenField: $bool:true
            targetColumn: {tablename: machines, column: machine_id, dataType: string}
            preFilledValue:
                valueRef:
                    tablename: machines
                    column: machine_id
                    queryParams:
                        limit: 1
                        filterAnd:
                            - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
                            - {column: machine_id, operator: '=', value: '2', dataType: string, useRoute: true}
          - label: $str:Deleted
            type: $str:checkbox
            hiddenField: $bool:true
            defaultValueBoolean: $bool:true
            targetColumn: {tablename: machines, column: deleted, dataType: boolean}
```

In the table variant, the same delete form has `openParameter: $str:delete`
in place of `formButtonStyle` and `submitNavigationRoute`, and its key field
filters with `{column: machine_id, operator: '=', value: delete, dataType:
string, useFilter: true}` in place of the `useRoute` condition.

## Uploading files with a form

A widget-form field with `type: $str:file` uploads one file into a FleetFiles
namespace of the app and writes the stored file's key into its `targetColumn`, in
the same save as the rest of the row (widget-form 1.0.38 and later):

```yaml
- label: $str:SOP document
  type: $str:file
  required: $bool:true
  targetColumn: {tablename: sop_commands, column: file_key, dataType: string}
  fileNamespace: $str:sop                    # a name from files.namespaces
  acceptedFileTypes: $str:application/pdf    # MIME types; image/* works too
  maxFileSizeMB: $num:6
  fileSizeColumn: {tablename: sop_commands, column: size_bytes, dataType: bigint}
```

- The target is a string column. It gets the key within the namespace,
  `<YYYY-MM-DD>/<random>/<file name>`: the last segment is the original file name,
  extension included. The app's code reads the file with the SDK's files API under
  that key and namespace.
- `fileNamespace` must be in the app's `files.namespaces` in data-template.yml
  (with none declared, only `default` exists). Keep `acceptedFileTypes` within the
  namespace's `contentTypes` and `maxFileSizeMB` within its `maxObjectBytes`. The
  validator checks all three.
- Files up to 6 MB upload on every installation. Larger ones need a presigned
  upload, which an appliance cannot issue, so a board that runs on an appliance
  keeps `maxFileSizeMB` at 6 or below.
- `fileNameColumn` (string), `fileSizeColumn` (bigint or numeric) and
  `fileTypeColumn` (string) are optional, belong in the target column's table, and
  are written only with a new file.
- In an edit form (above), bind `preFilledValue` to the record's key column:
  the form shows that file, and a save without a new file keeps it.
- Uploading needs the Use right on the app, like every form write. It does not work on an
  appliance opened through the cloud; there the form says to open the board on
  the appliance itself.
- A file field holds one file per record. For several photos per save, use a
  media field (next section).

## Photos with a form

A widget-form field with `type: $str:media` (widget-form 2.3.0 and later) takes
several photos in one save: taken with the phone's camera, picked from its
library, or chosen or dropped on a computer. Each photo is resized to a JPEG,
stored in a FleetFiles namespace, and written as **a row of its own** into the
table of the field's `targetColumn`, the photo table. Use it for a report or an
inspection made on a phone with photos as evidence, and for a form that adds
photos to a record that already exists. For one document per record, such as a
PDF manual, use a file field (above).

### The data model

The record and its photos are two entity tables, each keyed by an ID the form
generates, and the photo table carries the record's key as its link column
(app-templates.md, "One table per entity"):

```yaml
data:
  tables:
    - tablename: inspection_reports
      description: Inspection reports made on a phone at the asset.
      maintainLatestFlagFor: [report_id]
      columns:
        - {id: tsp, name: Timestamp, description: Time the report was saved (UTC), dataType: timestamp}
        - {id: report_id, name: Report, description: Report identifier (a UUID the form generates), dataType: string}
        - {id: asset_id, name: Asset, description: The inspected asset, dataType: string}
        - {id: note, name: Note, description: What the inspector found, dataType: string}
    - tablename: report_photos
      description: Photos of inspection reports, one row per photo.
      maintainLatestFlagFor: [photo_id]
      columns:
        - {id: tsp, name: Timestamp, description: Time the photo row was saved (UTC), dataType: timestamp}
        - {id: photo_id, name: Photo, description: Photo identifier (a UUID the form generates), dataType: string}
        - {id: report_id, name: Report, description: The report the photo belongs to, dataType: string}
        - {id: file_key, name: File key, description: Key of the photo in the namespace photos, dataType: string}
        - {id: file_name, name: File name, description: Original name of the photo, dataType: string}
        - {id: size_bytes, name: Size, description: Size of the stored photo in bytes, dataType: bigint}
        - {id: content_type, name: Content type, description: MIME type of the stored photo, dataType: string}
        - {id: file_url, name: URL, description: Platform URL of the stored photo, dataType: string}
        - {id: captured_at, name: Taken at, description: Time the photo was taken (UTC), dataType: timestamp}
        - {id: latitude, name: Latitude, description: Latitude in decimal degrees, dataType: numeric}
        - {id: longitude, name: Longitude, description: Longitude in decimal degrees, dataType: numeric}
        - {id: altitude, name: Altitude, description: Altitude in metres above sea level, dataType: numeric}
        - {id: position_source, name: Position source, description: Where the position came from (exif or device), dataType: string}
files:
  description: Photos taken with the board's report form.
  namespaces:
    - name: photos
      description: Report photos, resized to JPEG on the phone.
      contentTypes: ["image/jpeg"]
      maxObjectBytes: 10485760
```

Only `photo_id`, the link column and `file_key` are needed; leave out the
columns the app does not use. Set position columns only when the app needs to
know where a photo was taken: a person's position is personal data, and with
no position column the form never reads it or asks for it.

### A form that creates a record with photos

The record's key comes from a hidden Generate New ID field, and
`mediaLinkField` names that field by its Label so every photo row gets the
same value in `mediaLinkColumn`:

```yaml
formFields:
    - label: $str:Report ID
      type: $str:textfield
      hiddenField: $bool:true
      generateId: $bool:true
      targetColumn: {tablename: inspection_reports, column: report_id, dataType: string}
    - label: $str:Asset
      type: $str:textfield
      required: $bool:true
      targetColumn: {tablename: inspection_reports, column: asset_id, dataType: string}
    - label: $str:What did you find?
      type: $str:textarea
      targetColumn: {tablename: inspection_reports, column: note, dataType: string}
    - label: $str:Photos
      type: $str:media
      required: $bool:true                     # at least one photo
      cameraCapture: $bool:true                # a phone opens the rear camera at once
      maxPhotos: $num:10
      targetColumn: {tablename: report_photos, column: file_key, dataType: string}
      fileNamespace: $str:photos
      mediaIdColumn: {tablename: report_photos, column: photo_id, dataType: string}
      mediaLinkField: $str:Report ID           # the Label of the field above
      mediaLinkColumn: {tablename: report_photos, column: report_id, dataType: string}
      fileNameColumn: {tablename: report_photos, column: file_name, dataType: string}
      fileUrlColumn: {tablename: report_photos, column: file_url, dataType: string}
      capturedAtColumn: {tablename: report_photos, column: captured_at, dataType: timestamp}
      latitudeColumn: {tablename: report_photos, column: latitude, dataType: numeric}
      longitudeColumn: {tablename: report_photos, column: longitude, dataType: numeric}
      positionSourceColumn: {tablename: report_photos, column: position_source, dataType: string}
```

### A form that adds photos to an existing record

It writes no record row, only photo rows. A hidden field pre-filled with the
record's key targets the photo table's link column: every field whose
`targetColumn` is in the photo table goes into every photo row instead of a
row of its own, so no `mediaLinkField` is needed. Bind the pre-filled value
the way an edit form does (above, and board-assets.md):

```yaml
formFields:
    - label: $str:Report
      type: $str:textfield
      hiddenField: $bool:true
      targetColumn: {tablename: report_photos, column: report_id, dataType: string}
      preFilledValue:
          valueRef:
              tablename: inspection_reports
              column: report_id
              queryParams:
                  limit: 1
                  filterAnd:
                      - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
                      - {column: report_id, operator: '=', value: '2', dataType: string, useRoute: true}
    - label: $str:More photos
      type: $str:media
      required: $bool:true
      targetColumn: {tablename: report_photos, column: file_key, dataType: string}
      fileNamespace: $str:photos
      mediaIdColumn: {tablename: report_photos, column: photo_id, dataType: string}
```

### The rules

- `targetColumn` is the photo table's string column for the stored key. Every
  companion column belongs in the same table: `mediaIdColumn`,
  `mediaLinkColumn`, `fileNameColumn`, `fileTypeColumn`, `fileUrlColumn` and
  `positionSourceColumn` (string), `fileSizeColumn` (bigint or numeric),
  `capturedAtColumn` (timestamp), `latitudeColumn`, `longitudeColumn` and
  `altitudeColumn` (numeric).
- `mediaIdColumn` gets a new UUID per photo. Make it the photo table's entity
  key (`maintainLatestFlagFor`): a save repeated after a failure writes the
  same IDs again, which an entity table takes as a new version of the same
  photo rather than a second photo.
- `mediaLinkField` (the Label of another, non-section field of the same form)
  and `mediaLinkColumn` go together. The save is refused while the named field
  is empty.
- Every photo is turned upright and stored as a JPEG whose longer edge is at
  most `maxImageEdge` pixels (default 2048) at `imageQuality` 1 to 100
  (default 85), which keeps it under the 6 MB that uploads on every
  installation. So the namespace must take `image/jpeg`. `acceptedFileTypes`
  takes image types only and defaults to `image/*`; a photo the browser cannot
  decode (HEIC outside Safari) is uploaded as it is, which the namespace
  refuses unless it lists that type too. `maxFileSizeMB` applies to each photo
  after resizing.
- `cameraCapture` makes a phone open the rear camera directly, one photo at a
  time; without it the phone offers camera, library and files. `maxPhotos`
  caps the photos per save, and `required` asks for at least one.
- Position: from the photo's EXIF GPS data, else, for a photo just taken, the
  device's position once the viewer allows it. The device position needs an
  https board, so on an appliance served over http only EXIF positions are
  stored. A photo picked from the library without GPS data gets no position
  (phones may remove it when a web page picks the photo), and a photo without
  either leaves the columns empty and still saves.
- The photo rows are written before the form's own row, so a record row that
  exists has its photos. A form with a media field keeps its Submit button even
  with `autoSubmit`.

### Limits

- Studio stores every photo first (a failed upload writes no row), then
  writes the photo rows in one bulk insert, all or none, and the record's row
  after them. Where the router does not allow board sessions the bulk topic
  yet (an appliance not yet updated), the rows go out one by one and those
  before a failed one stay written. Either way the form keeps its values and
  the stored photos' keys, and Submit retries with the same IDs without
  uploading those photos again; the entity keys above make the retry
  harmless.
- Stored photos stay in the namespace when a save fails later: board sessions
  cannot delete files.
- It needs widget-form 2.3.0 or later and a Studio that handles the media save
  (`media-data-submit`). An older Studio leaves it unhandled, and the form says
  it cannot upload and saves nothing. As with file fields, uploading does not
  work on an appliance opened through the cloud.
- The validator checks the namespace (declared, takes `image/jpeg`), the
  accepted types (images within the namespace), the photo table's columns and
  their types, the link settings and the ID column's entity key.
