# Forms for records

This reference covers the file side of boards on which users create, edit and
delete records (master data, settings, assets): how the shape of
board-assets.md maps onto the navigation patterns of board-navigation.md, the
delete form in YAML, and uploading files with a form. The rules themselves (the
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
          bgColor: $str:#d32f2f
      accentColor: $str:#d32f2f         # the dialog's Delete button
      buttonLabels:
          submitLabel: $str:Delete
          cancelLabel: $str:Keep
      submitNavigationRoute: $str:/settings/machines
      formFields:                       # exactly these two, both hidden
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
