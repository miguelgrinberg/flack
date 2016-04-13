'use strict';
var app = app || {};

// MessageList represents a collection of messages, as returned by the server.
app.MessageList = Backbone.Collection.extend({
    url: '/api/messages',

    parse: function(response) {
        return response.messages;
    }
});
