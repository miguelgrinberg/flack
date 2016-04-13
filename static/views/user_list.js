'use strict';
var app = app || {};

// UserListView handles the user list portion of the page.
app.UserListView = Backbone.View.extend({
    el: '#participants',
    updated_since: 0,

    initialize: function(options) {
        _.bindAll(this, 'updateUser', 'render', 'refresh');

        // Keep a reference to the user collection.
        this.collection = options.collection;
    },

    updateUser: function(user) {
        // If this is a user that we already have, just update the model.
        if (this.collection.get(user.get('id'))) {
            this.collection.add(user, {merge: true});
            return;
        }

        // Add the new user to the collection, and insert it in the proper
        // place in the page.
        this.collection.add(user);
        var index = this.collection.indexOf(user);
        var prev = this.collection.at(index - 1);
        var userView = new app.UserView({tagName: 'li', model: user});
        if (index != 0) {
            this.$el.children(':nth-child(' + index + ')').after(
                userView.render().el);
        }
        else {
            this.$el.prepend(userView.render().el);
        }
    },

    render: function(updates) {
        // Update the list of user models one by one.
        updates = updates || this.collection;
        updates.forEach(function(user) {
            this.updateUser(user);
        }, this);
    },

    refresh: function(cb) {
        // Obtain list of user updates from the server.
        var users = new app.UserList();
        users.fetch({
            data: {updated_since: this.updated_since},
            success: function() {
                // Render the new or updated users.
                this.render(users);
                if (users.length > 0) {
                    this.updated_since =
                        users.at(users.length - 1).get('updated_at');
                }
                if (cb)
                    cb();
            }.bind(this),
        });
    },
});
