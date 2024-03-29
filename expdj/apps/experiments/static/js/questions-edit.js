/*global window, document, jQuery, Handsontable, NVMetadata */
(function ($) {
  'use strict';

  function emptyOrSpaced(value) {
    return !(value && /\S/.test(value));
  }

  function stringRequiredValidator(value, callback) {
    if (emptyOrSpaced(value)) {
      return callback(false);
    } else {
      return callback(true);
    }
  }

  function columnName(header) {
    return header.verboseName ? header.verboseName : header.name;
  }

  /*function headerNames(headers) {
    return headers.map(function (x) {
      if (x.required) {
        return columnName(x) + '*';
      }
      return columnName(x);
    });
  }*/

  function guessFieldType(field) {
    if (field.datasource) {
      return 'autocomplete';
    } else {
      return 'text';
    }
  }

  function getDataSource(field) {
    var datasource = field.datasource;

    if (datasource && datasource.choices) {
      return Questions.datasources[datasource.choices];
    } else {
      return undefined;
    }
  }

  function choiceValidator(choices) {
    return function (value, callback) {
      if (!value) {
        return callback(true);
      }
      var elems = Questions.datasources[choices].filter(function (x) {
        return x === value;
      });
      if (elems.length === 0) {
        return callback(false);
      }
      return callback(true);
    };
  }

  function getFieldValidator(field) {
    if (field.required && !field.datasource) {
      return stringRequiredValidator;
    } else if (!field.required && field.datasource && field.datasource.choices) {
      return choiceValidator(field.datasource.choices);
    } else {
      return undefined;
    }
  }

  function columnSettings(headers) {
    return headers.map(function (x) {
      return {
        type: guessFieldType(x),
        source: getDataSource(x),
        strict: x.required,
        allowInvalid: !x.required,
        validator: getFieldValidator(x)
      };
    });
  }

  function getDefaultHeight(data) {
    var minHeight = 400,
      maxHeight = 500,
      rowHeight = 24;

    if ((data.length + 1) * rowHeight < minHeight) {
      return minHeight;
    } else {
      return maxHeight;
    }
  }

  function columnExist(name) {
    var value = name.trim(),
      elems = Questions.headers.filter(function (x) {
        return x.name === value;
      });

    return elems.length !== 0;
  }

  function isFixedColumn(index) {
    return Questions.headers[index].fixed;
  }

  function hasAnyValues(arr) {
    var i, len;
    for (i = 0, len = arr.length; i < len; i += 1) {
      if (!emptyOrSpaced(arr[i])) {
        return true;
      }
    }
    return false;
  }

  function filterEmptyRows(array) {
    return array.filter(function (x) {
      return hasAnyValues(x);
    });
  }

  function serializeTable(hotInstance) {
    return [window.Questions.headers.map(function (x) {
      return x.name;
    })].concat(filterEmptyRows(hotInstance.getData()));
  }

  function validateInput(value, success, failure) {
    if (emptyOrSpaced(value)) {
      failure();
    } else if (columnExist(value)) {
      failure("Column already exists");
    } else {
      success();
    }
  }

  function showError($el, msg) {
    $el.addClass('has-error');
    if (msg) {
      $('.help-block', $el).text(msg);
    }
  }

  function clearError($el) {
    $('.help-block', $el).empty();
    $el.removeClass('has-error');
  }

  function getNewColumnName(callback) {
    var $modalEl = $('#columnNameModal'),
      $submit = $('button[type="submit"]', $modalEl),
      $columnNameEl = $('#column-name'),
      $inputWrapper = $('.js-input-wrapper', $modalEl);

    $modalEl.on('shown.bs.modal', function () {
      $columnNameEl.focus().attr("autocomplete", "off");

      $columnNameEl.keyup(function () {
        validateInput($columnNameEl.val(), function () {
          $submit.prop('disabled', false);
          clearError($inputWrapper);
        }, function (msg) {
          $submit.prop('disabled', true);
          if (msg) {
            showError($inputWrapper, msg);
          }
        });
      });

      $('.js-name-form', $modalEl)
        .off('submit.modal')
        .on('submit.modal', function () {
          var name = $columnNameEl.val().trim();
          callback(name);
          $modalEl.modal('hide');
          $columnNameEl.val('');
          return false;
        });
    });

    $modalEl.on('hide.bs.modal', function () {
      $columnNameEl.val('');
      clearError($inputWrapper);
    });

    $modalEl.modal();
  }

  function insertDataColumn(index, name) {
    Questions.headers.splice(index, 0, {
      name: name
    });
    Questions.data.map(function (x) {
      x.splice(index, 0, '');
    });
  }

  function removeDataColumn(index) {
    Questions.headers.splice(index, 1);
    Questions.data.map(function (x) {
      x.splice(index, 1);
    });
  }

  function insertLocation(selection, key) {
    if (key === 'insert_column_left') {
      return selection[1];
    } else {
      return selection[3] + 1;
    }
  }

  function updateSettings(hotInstance) {
    hotInstance.updateSettings({
      data: window.Questions.data,
      //colHeaders: headerNames(window.Questions.headers),
      //columns: columnSettings(window.Questions.headers)
    });
  }

  function handleInsertColumn(hotInstance, selection, key) {
    hotInstance.deselectCell();

    getNewColumnName(function (name) {
      var index = insertLocation(selection, key);

      insertDataColumn(index, name);
      updateSettings(hotInstance);
      hotInstance.render();
    });
  }

  function handleRemoveColumn(hotInstance, selection) {
    removeDataColumn(selection[1]);
    updateSettings(hotInstance);
    hotInstance.render();
  }

  $(document).ready(function () {

    var container = document.getElementById('hot'),
      hot = new Handsontable(container, {
        data: window.Questions.data,
        colHeaders: headerNames(window.Questions.headers),
        //columns: columnSettings(window.Questions.headers),
        //columnSorting: true,
        //sortIndicator: true,
        rowHeaders: true,
        //height: getDefaultHeight(window.Questions.data),
        //allowInsertRow: false,
        //minSpareRows: 0,
        //maxRows: window.Questions.data.length,
        /*contextMenu: {
          callback: function (key) {
            if (key === 'insert_column_left' ||
              key === 'insert_column_right') {
              handleInsertColumn(hot, hot.getSelected(), key);
            } else if (key === 'remove_this_column') {
              handleRemoveColumn(hot, hot.getSelected());
            }
          },
          items: {
            'insert_column_left': {
              name: 'Insert column on the left',
              disabled: function () {
                return hot.getSelected()[1] === 0;
              }
            },
            'insert_column_right': {
              name: 'Insert column on the right'
            },
            'hsep2': '---------',
            'remove_this_column': {
              name: 'Remove column',
              disabled: function () {
                return isFixedColumn(hot.getSelected()[1]);
              }
            },
            'hsep3': '---------',
            'undo': {},
            'redo': {}
          }
        },
        cells: function (r, c) {
          if (c === 0) {
            return {
              readOnly: true
            };
          }
        }*/
      });

    $('.btn-save-metadata').click(function () {
      var $this = $(this);
      $this.prop('disabled', true);

      // Passing empty func to fix 'onQueueEmpty is not a function' error in hot
      hot.validateCells(function () {});

      $.ajax({
          type: 'POST',
          data: JSON.stringify(serializeTable(hot)),
          contentType: 'application/json; charset=utf-8'
        })
        .done(function () {
          console.log('done!')
          //window.location.replace('/collections/' + collectionId);
        })
        .fail(function (jqXHR, textStatus, errorThrown) {
          $this.prop('disabled', false);

          Questions.displayErrors($('.errors'),
            Questions.getErrors(jqXHR, textStatus, errorThrown));
        });
    });

    window.onbeforeunload = function () {
      if (hot.isUndoAvailable()) {
        return 'You have pending unsaved changes. ' +
          'Do you really want to discard them ?';
      }
    };
  });

}(jQuery));
