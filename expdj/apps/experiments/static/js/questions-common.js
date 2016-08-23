/*global window */
(function () {
  'use strict';

  window.Questions = window.NVMetadata || {};
  var Questions = window.Questions;

  function formatFieldsError(messages) {
    var result = '',
      fieldName;

    for (fieldName in messages) {
      if (messages.hasOwnProperty(fieldName)) {
        result += '<div class="row"><div class="col-md-3">' + fieldName + '</div> <div class="col-md-9">' + messages[fieldName].join('; ') + '</div></div>';
      }
    }

    return result;
  }

  function formatItemMessages(messages) {
    var result = '',
      i, len;

    for (i = 0, len = messages.length; i < len; i += 1) {
      result += formatFieldsError(messages[i]);
    }

    return result;
  }

  function formatMessages(messages) {
    var item, result = [];

    for (item in messages) {
      if (messages.hasOwnProperty(item)) {
        result.push({msg: '<strong>' + item + '</strong>' +
          formatItemMessages(messages[item])
        });
      }
    }

    return result;
  }


  /*jslint unparam: true */
  Questions.getErrors = function (jqXHR, textStatus, errorThrown) {
    var r = jqXHR.responseJSON,
      errors;

    if (r) {
      if (r.messages) {
        errors = formatMessages(r.messages);
      } else {
        errors = [{msg: r.message}];
      }
    } else {
      errors = [{
        msg: 'Error while submitting data to server: ' + errorThrown
      }];
    }

    return errors;
  };

  Questions.displayErrors = function ($el, errors) {
    var len = errors.length,
      i;

    $el.empty();

    for (i = 0; i < len; i += 1) {
      $el.append('<div class="row-error">' + errors[i].msg + '</div>');
    }
    $el.show();
  };
}());
