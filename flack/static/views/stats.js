'use strict';
var app = app || {};

// MessageView handles a rendering of a single message.
app.StatsView = Backbone.View.extend({
    el: '#stats',

    initialize: function(options) {
        _.bindAll(this, 'render');
    },

    render: function() {
        var model = new Backbone.Model({defaults: {requests_per_second: 0}});
        Backbone.sync('read', model, {
            url: '/stats',
            success: function(response) {
                // put request per stats on the page
                this.$el.html(response.requests_per_second.toFixed(1));
            }.bind(this),
            error: function() {
                // put request per stats on the page
                this.$el.html('--');
            }.bind(this),
        });
        return this;
    }
});
