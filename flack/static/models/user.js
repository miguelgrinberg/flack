'use strict';
var app = app || {};

// The User model wraps the user resource representation.
app.User = Backbone.Model.extend({
    defaults: function() {
        return {
            id: null,
            nickname: null,
            created_at: null,
            updated_at: null,
            last_seen_at: null,
            online: false
        }
    },

    urlRoot: '/api/users'
});
