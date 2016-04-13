'use strict';
var app = app || {};

// UserView handles a rendering of a single user.
app.UserView = Backbone.View.extend({
    tagName: 'span',
    template: _.template($('#user-template').html()),

    initialize: function(options) {
        _.bindAll(this, 'userColor', 'render');

        // Depending on the place where the user is rendered, offline users
        // may or may not need to be displayed.
        this.showOffline = options.showOffline || false;

        // The model for this view is a Message instance.
        this.model.bind('change', this.render);
    },

    userColor: function() {
        // Choose a color for the user using a simple hashing algorithm on
        // the nickname.
        var nickname = this.model.get('nickname');
        var sum = 0;
        for (var i = 0; i < nickname.length; i++)
            sum += nickname.charCodeAt(i);
        return sum % 120;
    },

    render: function() {
        // Render the user to the page.
        this.$el.html(this.template({user: this.model.toJSON()}));
        this.$el.attr('class', 'color' + this.userColor());

        if (!this.showOffline) {
            // Handle user visibility based on the online status.
            if (this.model.get('online')) {
                this.$el.show();
            }
            else {
                this.$el.hide();
            }
        }
        return this;
    }
});
