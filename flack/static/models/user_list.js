'use strict';
var app = app || {};

// A UserList represents a collection of users, as returned by the server.
app.UserList = Backbone.Collection.extend({
    url: '/api/users',
    comparator: 'nickname',  // sort by nickname

    parse: function(response) {
        return response.users;
    }
});
