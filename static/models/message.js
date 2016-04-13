'use strict';
var app = app || {};

// The Message model wraps the message resource representation.
app.Message = Backbone.Model.extend({
    defaults: function() {
        return {
            id: null,
            source: null,
            html: null,
            created_at: null,
            updated_at: null,
            user_id: null
        }
    },

    urlRoot: '/api/messages'
});
