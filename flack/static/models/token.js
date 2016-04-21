'use strict';
var app = app || {};

// A Token model represents a token returned by the server.
app.Token = Backbone.Model.extend({
    defaults: function() {
        return {
            'token': null
        }
    },
});
